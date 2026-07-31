import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import main


class FundEstimateFallbackTests(unittest.TestCase):
    def setUp(self):
        main._fund_quote_fallback_cache.clear()
        main._fund_meta_name_cache.clear()
        main._fund_estimate_cache.clear()

    def test_fetch_fund_estimate_falls_back_to_latest_nav_when_estimate_api_empty(self):
        df = pd.DataFrame(
            {
                "净值日期": pd.to_datetime(["2026-07-30", "2026-07-31"]),
                "单位净值": [3.063, 3.048],
            }
        )

        with (
            mock.patch.object(main, "_fetch_all_fund_estimates", return_value={}),
            mock.patch.object(main, "fetch_fund_history_data", return_value=df),
            mock.patch.object(main, "_fetch_fund_name", return_value="易方达消费行业股票"),
        ):
            result = main.fetch_fund_estimate("110022")

        self.assertEqual(result["name"], "易方达消费行业股票")
        self.assertEqual(result["current_nav"], 3.048)
        self.assertEqual(result["prev_nav"], 3.063)
        self.assertEqual(result["ts"], "2026-07-31")
        self.assertAlmostEqual(result["pct"], (3.048 - 3.063) / 3.063 * 100, places=4)

    def test_fetch_fund_falls_back_to_latest_nav_when_estimate_api_empty(self):
        df = pd.DataFrame(
            {
                "净值日期": pd.to_datetime(["2026-07-30", "2026-07-31"]),
                "单位净值": [3.063, 3.048],
            }
        )

        with (
            mock.patch.object(main, "_fetch_all_fund_estimates", return_value={}),
            mock.patch.object(main, "fetch_fund_history_data", return_value=df),
            mock.patch.object(main, "fund_history_stats", return_value={"chg3": 1.0}),
            mock.patch.object(main, "_fetch_fund_name", return_value="易方达消费行业股票"),
        ):
            result = main.fetch_fund("110022")

        self.assertEqual(result["name"], "易方达消费行业股票")
        self.assertEqual(result["current"], 3.048)
        self.assertEqual(result["prev_close"], 3.063)
        self.assertAlmostEqual(result["change"], -0.015, places=4)
        self.assertEqual(result["chg3"], 1.0)

    def test_fetch_fund_estimate_uses_real_time_estimate_when_available(self):
        fake_item = {
            "jjjc": "易方达消费行业股票",
            "gsz": "3.0500",
            "gszzl": "-0.42%",
            "dwjz": "3.063",
            "gxrq": "2026-07-31",
        }

        with mock.patch.object(main, "_fetch_all_fund_estimates", return_value={"110022": fake_item}):
            result = main.fetch_fund_estimate("110022")

        self.assertEqual(result["name"], "易方达消费行业股票")
        self.assertEqual(result["current_nav"], 3.05)
        self.assertEqual(result["prev_nav"], 3.063)
        self.assertAlmostEqual(result["pct"], -0.42, places=2)

    def test_fetch_fund_estimate_falls_back_when_estimate_item_lacks_value(self):
        fake_item = {"jjjc": "某基金", "gsz": "---", "gszzl": "---", "dwjz": "1.0000", "gxrq": "2026-07-31"}
        df = pd.DataFrame(
            {
                "净值日期": pd.to_datetime(["2026-07-30", "2026-07-31"]),
                "单位净值": [1.000, 1.010],
            }
        )

        with (
            mock.patch.object(main, "_fetch_all_fund_estimates", return_value={"110022": fake_item}),
            mock.patch.object(main, "fetch_fund_history_data", return_value=df),
            mock.patch.object(main, "_fetch_fund_name", return_value="某基金"),
        ):
            result = main.fetch_fund_estimate("110022")

        self.assertEqual(result["name"], "某基金")
        self.assertEqual(result["current_nav"], 1.010)
        self.assertAlmostEqual(result["pct"], 1.0, places=4)

    def test_fetch_all_fund_estimates_direct_returns_empty_when_data_is_null(self):
        resp = mock.Mock()
        resp.json.return_value = {"Data": None, "ErrCode": -1, "ErrMsg": "暂无数据"}

        with (
            mock.patch.object(main.requests, "get", return_value=resp),
            mock.patch.object(main.time_module, "time", return_value=1000.0),
        ):
            result = main._fetch_all_fund_estimates_direct()

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()

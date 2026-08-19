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

    def _history_df(self):
        return pd.DataFrame(
            {
                "净值日期": pd.to_datetime(["2026-07-30", "2026-07-31"]),
                "单位净值": [3.063, 3.048],
            }
        )

    def test_fetch_fund_valuation_last_requests_codes_and_normalizes_lookup(self):
        response = mock.Mock()
        response.json.return_value = {
            "success": True,
            "data": [
                {"FCODE": "110022", "SHORTNAME": "易方达消费行业股票", "GSZ": 3.05},
                {"FCODE": "161725", "SHORTNAME": "白酒指数", "GSZ": 0.55},
            ],
        }

        with mock.patch.object(main.requests, "get", return_value=response) as mock_get:
            result = main._fetch_fund_valuation_last(["161725", "110022", "161725"])

        self.assertEqual(set(result), {"110022", "161725"})
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(mock_get.call_args.kwargs["params"]["FCODES"], "161725,110022")
        self.assertEqual(
            mock_get.call_args.kwargs["params"]["FIELDS"],
            "FCODE,SHORTNAME,GSZZL,GZTIME,GSZ,NAV,PDATE",
        )

    def test_fetch_fund_valuation_last_falls_back_to_secondary_host(self):
        failed_response = mock.Mock()
        failed_response.json.return_value = {"success": False, "errorCode": 500, "firstError": "暂不可用"}
        success_response = mock.Mock()
        success_response.json.return_value = {"success": True, "data": [{"FCODE": "110022"}]}

        with mock.patch.object(main.requests, "get", side_effect=[failed_response, success_response]) as mock_get:
            result = main._fetch_fund_valuation_last(["110022"])

        self.assertIn("110022", result)
        self.assertEqual(mock_get.call_count, 2)
        self.assertIn(main.FUND_VALUATION_HOSTS[0], mock_get.call_args_list[0].args[0])
        self.assertIn(main.FUND_VALUATION_HOSTS[1], mock_get.call_args_list[1].args[0])

    def test_fetch_fund_valuation_last_uses_code_set_cache(self):
        response = mock.Mock()
        response.json.return_value = {"success": True, "data": [{"FCODE": "110022"}]}

        with (
            mock.patch.object(main.requests, "get", return_value=response) as mock_get,
            mock.patch.object(main.time_module, "time", side_effect=[1000.0, 1001.0]),
        ):
            main._fetch_fund_valuation_last(["110022", "161725"])
            main._fetch_fund_valuation_last(["161725", "110022"])

        self.assertEqual(mock_get.call_count, 1)

    def test_parse_fund_valuation_last_marks_complete_estimate(self):
        result = main._parse_fund_valuation_last(
            {
                "FCODE": "110022",
                "SHORTNAME": "易方达消费行业股票",
                "GSZ": 3.05,
                "GSZZL": -0.42,
                "GZTIME": "2026-08-19 10:40",
                "NAV": 3.063,
                "PDATE": "2026-08-18",
            },
            "110022",
        )

        self.assertEqual(result["quote_status"], "estimate")
        self.assertEqual(result["quote_label"], "盘中估值")
        self.assertEqual(result["est_nav"], 3.05)
        self.assertEqual(result["prev_nav"], 3.063)
        self.assertAlmostEqual(result["pct"], -0.42, places=2)

    def test_parse_fund_valuation_last_marks_missing_estimate_as_published_nav(self):
        result = main._parse_fund_valuation_last(
            {
                "FCODE": "110022",
                "SHORTNAME": "易方达消费行业股票",
                "GSZ": None,
                "GSZZL": None,
                "GZTIME": None,
                "NAV": 3.063,
                "PDATE": "2026-08-18",
            },
            "110022",
        )

        self.assertEqual(result["quote_status"], "published_nav")
        self.assertEqual(result["quote_label"], "已公布净值")
        self.assertEqual(result["est_nav"], 3.063)
        self.assertIsNone(result["pct"])
        self.assertEqual(result["ts"], "2026-08-18")

    def test_fetch_fund_estimates_uses_one_batch_request_and_keeps_quote_states(self):
        lookup = {
            "161725": {
                "FCODE": "161725",
                "SHORTNAME": "白酒指数",
                "GSZ": 0.5528,
                "GSZZL": -1.59,
                "GZTIME": "2026-08-19 10:40",
                "NAV": 0.5617,
                "PDATE": "2026-08-18",
            },
            "110022": {
                "FCODE": "110022",
                "SHORTNAME": "易方达消费行业股票",
                "GSZ": None,
                "GSZZL": None,
                "GZTIME": None,
                "NAV": 3.063,
                "PDATE": "2026-08-18",
            },
        }

        with mock.patch.object(main, "_fetch_fund_valuation_last", return_value=lookup) as mock_fetch:
            results = main.fetch_fund_estimates(["161725", "110022"])

        mock_fetch.assert_called_once_with(["161725", "110022"])
        self.assertEqual(results["161725"]["quote_status"], "estimate")
        self.assertEqual(results["110022"]["quote_status"], "published_nav")
        self.assertIsNone(results["110022"]["pct"])

    def test_fetch_fund_estimate_falls_back_to_latest_nav_when_new_api_has_no_item(self):
        with (
            mock.patch.object(main, "_fetch_fund_valuation_last", return_value={}),
            mock.patch.object(main, "fetch_fund_history_data", return_value=self._history_df()),
            mock.patch.object(main, "_fetch_fund_name", return_value="易方达消费行业股票"),
        ):
            result = main.fetch_fund_estimate("110022")

        self.assertEqual(result["name"], "易方达消费行业股票")
        self.assertEqual(result["quote_status"], "published_nav")
        self.assertEqual(result["current_nav"], 3.048)
        self.assertEqual(result["prev_nav"], 3.063)
        self.assertEqual(result["ts"], "2026-07-31")

    def test_fetch_fund_uses_history_previous_nav_for_published_quote(self):
        published_quote = {
            "name": "易方达消费行业股票",
            "current_nav": 3.048,
            "prev_nav": None,
            "pct": None,
            "change": None,
            "ts": "2026-07-31",
            "quote_status": "published_nav",
            "quote_label": "已公布净值",
        }

        with (
            mock.patch.object(main, "fetch_fund_estimates", return_value={"110022": published_quote}),
            mock.patch.object(main, "fund_history_stats", return_value={"chg3": 1.0, "history_prev_nav": 3.063}),
        ):
            result = main.fetch_fund("110022")

        self.assertEqual(result["quote_label"], "已公布净值")
        self.assertEqual(result["prev_close"], 3.063)
        self.assertAlmostEqual(result["change"], -0.015, places=4)
        self.assertAlmostEqual(result["pct"], (3.048 - 3.063) / 3.063 * 100, places=4)


if __name__ == "__main__":
    unittest.main()

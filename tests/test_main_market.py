import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import main


class MarketIndexFetchTests(unittest.TestCase):
    def _fake_quotes_get(self, fake_quotes: dict):
        def fake_get(url, params, headers, timeout):
            resp = mock.Mock()
            resp.json.return_value = fake_quotes.get(params.get("secid")) or {"data": None}
            return resp

        return fake_get

    def test_fetch_cn_indices_queries_eastmoney_by_secid_and_returns_normalized_rows(self):
        fake_quotes = {
            "1.000001": {"data": {"f43": 3100.12, "f169": 17.25, "f170": 0.56}},
        }

        with (
            mock.patch.object(main.requests, "get", side_effect=self._fake_quotes_get(fake_quotes)),
            mock.patch.object(main.time_module, "sleep"),
            mock.patch.object(
                main,
                "MARKET_INDEX_CONFIGS",
                [{"code": "000001", "name": "上证指数", "category": "上证系列指数"}],
            ),
        ):
            result = main.fetch_cn_indices()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["code"], "000001")
        self.assertEqual(result[0]["name"], "上证指数")
        self.assertEqual(result[0]["current"], 3100.12)
        self.assertEqual(result[0]["change"], 17.25)
        self.assertEqual(result[0]["pct"], 0.56)

    def test_fetch_cn_indices_skips_missing_index_and_keeps_available_ones(self):
        fake_quotes = {
            "1.000001": {"data": {"f43": 3100.12, "f169": 17.25, "f170": 0.56}},
        }

        with (
            mock.patch.object(main.requests, "get", side_effect=self._fake_quotes_get(fake_quotes)),
            mock.patch.object(main.time_module, "sleep"),
            mock.patch.object(
                main,
                "MARKET_INDEX_CONFIGS",
                [
                    {"code": "000001", "name": "上证指数", "category": "上证系列指数"},
                    {"code": "399001", "name": "深证成指", "category": "深证系列指数"},
                ],
            ),
        ):
            result = main.fetch_cn_indices()

        self.assertEqual([item["code"] for item in result], ["000001"])

    def test_fetch_cn_indices_raises_when_no_index_available(self):
        with (
            mock.patch.object(main.requests, "get", side_effect=self._fake_quotes_get({})),
            mock.patch.object(main.time_module, "sleep"),
            mock.patch.object(
                main,
                "MARKET_INDEX_CONFIGS",
                [{"code": "000001", "name": "上证指数", "category": "上证系列指数"}],
            ),
        ):
            with self.assertRaises(ValueError):
                main.fetch_cn_indices()

    def test_index_secid_maps_known_index_codes_to_eastmoney_market(self):
        self.assertEqual(main._index_secid("000001"), "1.000001")
        self.assertEqual(main._index_secid("000688"), "1.000688")
        self.assertEqual(main._index_secid("000016"), "1.000016")
        self.assertEqual(main._index_secid("000300"), "1.000300")
        self.assertEqual(main._index_secid("000905"), "1.000905")
        self.assertEqual(main._index_secid("000852"), "1.000852")
        self.assertEqual(main._index_secid("399001"), "0.399001")
        self.assertEqual(main._index_secid("399006"), "0.399006")
        self.assertEqual(main._index_secid("899050"), "0.899050")
        self.assertEqual(main._index_secid(""), "")


if __name__ == "__main__":
    unittest.main()

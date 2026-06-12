import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import main


class MarketIndexFetchTests(unittest.TestCase):
    def test_fetch_cn_indices_still_works_when_packaged_stdio_is_none(self):
        df = pd.DataFrame(
            [
                {"代码": "000001", "最新价": 3100.12, "涨跌幅": 0.56, "涨跌额": 17.25},
            ]
        )

        def fake_stock_zh_index_spot_em():
            if sys.stdout is None or sys.stderr is None:
                raise AttributeError("'NoneType' object has no attribute 'write'")
            return df

        with (
            mock.patch.object(main.ak, "stock_zh_index_spot_em", side_effect=fake_stock_zh_index_spot_em),
            mock.patch.object(main.time_module, "sleep"),
            mock.patch.object(main, "MARKET_INDEX_CONFIGS", [{"code": "000001", "name": "上证指数", "category": "上证系列指数"}]),
            mock.patch.object(sys, "stdout", None),
            mock.patch.object(sys, "stderr", None),
        ):
            result = main.fetch_cn_indices()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["code"], "000001")
        self.assertEqual(result[0]["name"], "上证指数")
        self.assertEqual(result[0]["current"], 3100.12)
        self.assertEqual(result[0]["change"], 17.25)
        self.assertEqual(result[0]["pct"], 0.56)


if __name__ == "__main__":
    unittest.main()

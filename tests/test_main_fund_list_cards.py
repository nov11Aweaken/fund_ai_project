import types
import unittest

from main import FletApp


class FundListCardHelperTests(unittest.TestCase):
    def test_build_fund_overview_metrics_returns_four_modern_metric_blocks(self):
        dummy_app = types.SimpleNamespace()

        metrics = FletApp._build_fund_overview_metrics(
            dummy_app,
            {
                "est_pct": 1.28,
                "prev_day_pct": 0.63,
                "holding_units": 1234.56,
                "holding_cost_amount": 1500.0,
                "daily_profit": 15.82,
                "total_profit": 106.31,
            },
            "3-19净值变化",
        )

        self.assertEqual([m["label"] for m in metrics], ["行情", "持仓", "当日盈亏", "累计盈亏"])
        self.assertEqual(metrics[0]["primary"], "+1.28%")
        self.assertEqual(metrics[0]["secondary"], "3-19净值变化 +0.63%")
        self.assertEqual(metrics[1]["primary"], "1234.56份")
        self.assertEqual(metrics[1]["secondary"], "持仓成本 ¥1500.00")
        self.assertEqual(metrics[2]["primary"], "+¥15.82")
        self.assertEqual(metrics[3]["primary"], "+¥106.31")

    def test_fund_list_sort_summary_describes_active_sort(self):
        dummy_app = types.SimpleNamespace(_fund_list_sort_field="est_pct", _fund_list_sort_desc=True)

        summary = FletApp._fund_list_sort_summary(dummy_app)

        self.assertEqual(summary, "按实时估值降序")


if __name__ == "__main__":
    unittest.main()

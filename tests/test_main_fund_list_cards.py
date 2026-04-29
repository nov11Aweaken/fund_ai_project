import types
import unittest

from main import FletApp, DOWN, UP, VALUE_TEXT, SUBTEXT


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
        self.assertEqual(metrics[0]["secondary_label"], "3-19净值变化")
        self.assertEqual(metrics[0]["secondary_value"], "+0.63%")
        self.assertEqual(metrics[0]["secondary_color"], UP)
        self.assertEqual(metrics[1]["primary"], "1234.56份")
        self.assertEqual(metrics[1]["secondary"], "持仓成本 ¥1500.00")
        self.assertEqual(metrics[2]["primary"], "+¥15.82")
        self.assertEqual(metrics[3]["primary"], "+¥106.31")

    def test_build_fund_overview_metrics_uses_neutral_color_for_flat_previous_day_pct(self):
        dummy_app = types.SimpleNamespace()

        metrics = FletApp._build_fund_overview_metrics(
            dummy_app,
            {
                "est_pct": -0.18,
                "prev_day_pct": 0.0,
            },
            "上一日涨跌幅",
        )

        self.assertEqual(metrics[0]["secondary"], "上一日涨跌幅 0.00%")
        self.assertEqual(metrics[0]["secondary_label"], "上一日涨跌幅")
        self.assertEqual(metrics[0]["secondary_value"], "0.00%")
        self.assertEqual(metrics[0]["secondary_color"], VALUE_TEXT)
        self.assertEqual(metrics[0]["color"], DOWN)

    def test_fund_list_sort_summary_describes_active_sort(self):
        dummy_app = types.SimpleNamespace(_fund_list_sort_field="est_pct", _fund_list_sort_desc=True)

        summary = FletApp._fund_list_sort_summary(dummy_app)

        self.assertEqual(summary, "按实时估值降序")

    def test_build_fund_list_market_row_places_prev_metric_before_primary_value(self):
        dummy_app = types.SimpleNamespace()
        row = FletApp._build_fund_list_market_row(
            dummy_app,
            {
                "primary": "+1.28%",
                "color": UP,
                "secondary_label": "昨净",
                "secondary_value": "-0.63%",
                "secondary_color": DOWN,
            },
        )
        self.assertEqual(row.controls[0].value, "昨净")
        self.assertEqual(row.controls[1].value, "-0.63%")
        self.assertEqual(row.controls[2].value, "+1.28%")

    def test_build_fund_list_market_row_uses_weaker_style_for_secondary_metric(self):
        dummy_app = types.SimpleNamespace()
        row = FletApp._build_fund_list_market_row(
            dummy_app,
            {
                "primary": "+1.28%",
                "color": UP,
                "secondary_label": "昨净",
                "secondary_value": "-0.63%",
                "secondary_color": DOWN,
            },
        )
        self.assertLess(row.controls[0].size, row.controls[2].size)
        self.assertLess(row.controls[1].size, row.controls[2].size)
        self.assertEqual(row.controls[1].color, DOWN)
        self.assertNotEqual(row.controls[2].weight, row.controls[1].weight)

    def test_build_fund_list_market_row_keeps_single_line_with_missing_secondary_value(self):
        dummy_app = types.SimpleNamespace()
        row = FletApp._build_fund_list_market_row(
            dummy_app,
            {
                "primary": "--",
                "color": SUBTEXT,
                "secondary_label": "昨净",
                "secondary_value": "--",
                "secondary_color": VALUE_TEXT,
            },
        )
        self.assertEqual(len(row.controls), 3)
        self.assertEqual(row.controls[1].value, "--")
        self.assertEqual(row.controls[2].value, "--")


if __name__ == "__main__":
    unittest.main()

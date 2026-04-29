import types
import unittest

import flet as ft

from main import FletApp, DOWN, SUBTEXT, UP, VALUE_TEXT


class FundListCardHelperTests(unittest.TestCase):
    def test_build_fund_list_market_row_places_secondary_metric_before_primary(self):
        row = FletApp._build_fund_list_market_row(
            types.SimpleNamespace(),
            {
                "secondary_label": "昨净",
                "secondary_value": "+0.63%",
                "secondary_color": UP,
                "primary": "+1.28%",
                "color": UP,
            },
        )

        self.assertIsInstance(row, ft.Row)
        self.assertEqual(row.controls[0].value, "昨净")
        self.assertEqual(row.controls[1].value, "+0.63%")
        self.assertEqual(row.controls[2].value, "+1.28%")

    def test_build_fund_list_market_row_uses_weaker_secondary_metric_styling(self):
        row = FletApp._build_fund_list_market_row(
            types.SimpleNamespace(),
            {
                "secondary_label": "昨净",
                "secondary_value": "-0.63%",
                "secondary_color": DOWN,
                "primary": "+1.28%",
                "color": UP,
            },
        )

        secondary_label = row.controls[0]
        secondary_value = row.controls[1]
        primary = row.controls[2]

        self.assertLess(secondary_label.size, primary.size)
        self.assertLess(secondary_value.size, primary.size)
        self.assertEqual(secondary_label.color, SUBTEXT)
        self.assertEqual(secondary_value.color, DOWN)
        self.assertNotEqual(primary.weight, secondary_value.weight)

    def test_build_fund_list_market_row_keeps_three_controls_for_missing_secondary_value(self):
        row = FletApp._build_fund_list_market_row(
            types.SimpleNamespace(),
            {
                "secondary_label": "昨净",
                "secondary_value": "--",
                "secondary_color": SUBTEXT,
                "primary": "--",
                "color": SUBTEXT,
            },
        )

        self.assertIsInstance(row, ft.Row)
        self.assertEqual(len(row.controls), 3)
        self.assertEqual(row.controls[0].value, "昨净")
        self.assertEqual(row.controls[1].value, "--")
        self.assertEqual(row.controls[2].value, "--")
        self.assertEqual(row.spacing, 8)
        self.assertEqual(row.alignment, ft.MainAxisAlignment.END)
        self.assertEqual(row.vertical_alignment, ft.CrossAxisAlignment.CENTER)

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
        self.assertEqual(metrics[0]["secondary"], "昨净 +0.63%")
        self.assertEqual(metrics[0]["secondary_label"], "昨净")
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

        self.assertEqual(metrics[0]["secondary"], "昨净 0.00%")
        self.assertEqual(metrics[0]["secondary_label"], "昨净")
        self.assertEqual(metrics[0]["secondary_value"], "0.00%")
        self.assertEqual(metrics[0]["secondary_color"], VALUE_TEXT)
        self.assertEqual(metrics[0]["color"], DOWN)

    def test_build_fund_overview_metrics_uses_compact_prev_label_for_market_secondary(self):
        dummy_app = types.SimpleNamespace()
        metrics = FletApp._build_fund_overview_metrics(
            dummy_app,
            {"est_pct": 1.28, "prev_day_pct": -0.63},
            "3-19净值变化",
        )
        self.assertEqual(metrics[0]["secondary_label"], "昨净")
        self.assertEqual(metrics[0]["secondary_value"], "-0.63%")

    def test_build_fund_overview_metrics_reuses_existing_market_colors_for_secondary_metric(self):
        dummy_app = types.SimpleNamespace()
        positive_metrics = FletApp._build_fund_overview_metrics(
            dummy_app,
            {"est_pct": 1.28, "prev_day_pct": 0.63},
            "上一交易日净值变化",
        )
        negative_metrics = FletApp._build_fund_overview_metrics(
            dummy_app,
            {"est_pct": 1.28, "prev_day_pct": -0.63},
            "上一交易日净值变化",
        )
        self.assertEqual(positive_metrics[0]["secondary_color"], UP)
        self.assertEqual(negative_metrics[0]["secondary_color"], DOWN)

    def test_build_fund_overview_metrics_uses_placeholder_for_missing_prev_metric(self):
        dummy_app = types.SimpleNamespace()
        metrics = FletApp._build_fund_overview_metrics(
            dummy_app,
            {"est_pct": 1.28, "prev_day_pct": None},
            "上一交易日净值变化",
        )
        self.assertEqual(metrics[0]["secondary_label"], "昨净")
        self.assertEqual(metrics[0]["secondary_value"], "--")

    def test_build_fund_overview_metrics_keeps_primary_placeholder_when_est_pct_missing(self):
        dummy_app = types.SimpleNamespace()
        metrics = FletApp._build_fund_overview_metrics(
            dummy_app,
            {"est_pct": None, "prev_day_pct": -0.63},
            "上一交易日净值变化",
        )
        self.assertEqual(metrics[0]["primary"], "--")

    def test_fund_list_sort_summary_describes_active_sort(self):
        dummy_app = types.SimpleNamespace(_fund_list_sort_field="est_pct", _fund_list_sort_desc=True)

        summary = FletApp._fund_list_sort_summary(dummy_app)

        self.assertEqual(summary, "按实时估值降序")


if __name__ == "__main__":
    unittest.main()

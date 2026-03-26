import types
import unittest

import flet as ft

from main import FletApp


class PageRedesignHelperTests(unittest.TestCase):
    def test_build_market_overview_card_data_exposes_three_key_metrics(self):
        dummy_app = types.SimpleNamespace()

        card = FletApp._build_market_overview_card_data(
            dummy_app,
            {
                "name": "上证指数",
                "code": "000001",
                "price": 3210.12,
                "chg": -12.56,
                "pct": -0.39,
            },
        )

        self.assertEqual(card["title"], "上证指数")
        self.assertEqual(card["subtitle"], "代码 000001")
        self.assertEqual([item["label"] for item in card["metrics"]], ["最新价", "涨跌", "涨跌幅"])
        self.assertEqual(card["metrics"][0]["value"], "3210.12")
        self.assertEqual(card["metrics"][1]["value"], "-12.56")
        self.assertEqual(card["metrics"][2]["value"], "-0.39%")

    def test_build_market_dense_row_data_repackages_three_metrics_for_single_row_layout(self):
        dummy_app = types.SimpleNamespace(
            _build_market_overview_card_data=lambda item: FletApp._build_market_overview_card_data(
                types.SimpleNamespace(),
                item,
            )
        )

        row = FletApp._build_market_dense_row_data(
            dummy_app,
            {
                "name": "上证指数",
                "code": "000001",
                "price": 3210.12,
                "chg": -12.56,
                "pct": -0.39,
            },
        )

        self.assertEqual(row["title"], "上证指数")
        self.assertEqual(row["code"], "000001")
        self.assertEqual(row["price"]["value"], "3210.12")
        self.assertEqual(row["change"]["value"], "-12.56")
        self.assertEqual(row["pct"]["value"], "-0.39%")

    def test_build_fund_detail_holding_metrics_includes_profit_blocks(self):
        dummy_app = types.SimpleNamespace()

        metrics = FletApp._build_fund_detail_holding_metrics(
            dummy_app,
            {
                "holding_units": 1234.56,
                "holding_cost_amount": 1500.0,
                "daily_profit": 12.34,
                "total_profit": 56.78,
            },
        )

        self.assertEqual(
            [item["label"] for item in metrics],
            ["持仓份额", "持仓成本", "当日盈亏", "累计盈亏"],
        )
        self.assertEqual(metrics[0]["value"], "1234.56份")
        self.assertEqual(metrics[1]["value"], "¥1500.00")
        self.assertEqual(metrics[2]["value"], "+¥12.34")
        self.assertEqual(metrics[3]["value"], "+¥56.78")

    def test_build_metric_wrap_row_returns_responsive_row(self):
        dummy_app = types.SimpleNamespace()

        row = FletApp._build_metric_wrap_row(
            dummy_app,
            [ft.Container(), ft.Container()],
        )

        self.assertIsInstance(row, ft.ResponsiveRow)
        self.assertEqual(row.spacing, 12)
        self.assertEqual(row.run_spacing, 12)

    def test_create_metric_tile_uses_responsive_columns(self):
        dummy_app = types.SimpleNamespace(
            _module_card=lambda content, padding=12, expand=None: ft.Container(
                content=content,
                padding=padding,
                expand=expand,
            )
        )

        tile = FletApp._create_metric_tile(dummy_app, "持仓份额")

        self.assertEqual(tile["wrapper"].col, {"xs": 12, "sm": 6, "xl": 3})

    def test_detail_holding_action_config_uses_add_icon_without_holding(self):
        dummy_app = types.SimpleNamespace(
            _get_fund_config_item=lambda code: {"code": code},
        )

        config = FletApp._detail_holding_action_config(dummy_app, "110022")

        self.assertEqual(config["icon"], ft.Icons.ADD_CARD)
        self.assertEqual(config["tooltip"], "录入持仓")

    def test_detail_holding_action_config_uses_edit_icon_with_holding(self):
        dummy_app = types.SimpleNamespace(
            _get_fund_config_item=lambda code: {"code": code, "holding": {"units": 10, "cost_amount": 12}},
        )

        config = FletApp._detail_holding_action_config(dummy_app, "110022")

        self.assertEqual(config["icon"], ft.Icons.EDIT_NOTE)
        self.assertEqual(config["tooltip"], "编辑持仓")

    def test_build_fund_detail_panel_enables_vertical_scroll(self):
        dummy_app = types.SimpleNamespace()

        panel = FletApp._build_fund_detail_panel(dummy_app, ft.Container())

        self.assertIsInstance(panel, ft.Column)
        self.assertEqual(panel.scroll, ft.ScrollMode.AUTO)
        self.assertTrue(panel.expand)


if __name__ == "__main__":
    unittest.main()

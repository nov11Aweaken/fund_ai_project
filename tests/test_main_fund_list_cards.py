import types
import unittest

import flet as ft

from main import ACCENT, FletApp, DOWN, SUBTEXT, UP, VALUE_TEXT


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
        self.assertEqual(len(row.controls), 2)
        secondary_group = row.controls[0]
        primary_capsule = row.controls[1]
        self.assertIsInstance(secondary_group, ft.Row)
        self.assertIsInstance(primary_capsule, ft.Container)
        self.assertEqual(secondary_group.controls[0].value, "昨净")
        self.assertEqual(secondary_group.controls[1].value, "+0.63%")
        self.assertEqual(primary_capsule.content.value, "+1.28%")

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

        secondary_group = row.controls[0]
        secondary_label = secondary_group.controls[0]
        secondary_value = secondary_group.controls[1]
        primary_capsule = row.controls[1]

        self.assertLess(secondary_label.size, primary_capsule.content.size)
        self.assertLess(secondary_value.size, primary_capsule.content.size)
        self.assertEqual(secondary_label.color, SUBTEXT)
        self.assertEqual(secondary_value.color, DOWN)
        self.assertNotEqual(primary_capsule.content.weight, secondary_value.weight)

    def test_build_fund_list_market_row_keeps_grouped_placeholder_when_secondary_value_key_missing(self):
        row = FletApp._build_fund_list_market_row(
            types.SimpleNamespace(),
            {
                "secondary_label": "昨净",
                "secondary_color": SUBTEXT,
                "primary": "--",
                "color": SUBTEXT,
            },
        )

        self.assertIsInstance(row, ft.Row)
        self.assertEqual(len(row.controls), 2)
        secondary_group = row.controls[0]
        primary_capsule = row.controls[1]
        self.assertIsInstance(secondary_group, ft.Row)
        self.assertIsInstance(primary_capsule, ft.Container)
        self.assertEqual(secondary_group.controls[0].value, "昨净")
        self.assertEqual(secondary_group.controls[1].value, "--")
        self.assertEqual(secondary_group.controls[1].color, SUBTEXT)
        self.assertEqual(primary_capsule.content.value, "--")
        self.assertEqual(primary_capsule.content.color, SUBTEXT)
        self.assertEqual(secondary_group.spacing, 4)
        self.assertEqual(row.spacing, 14)
        self.assertEqual(row.alignment, ft.MainAxisAlignment.END)
        self.assertEqual(row.vertical_alignment, ft.CrossAxisAlignment.CENTER)

    def test_build_fund_list_market_row_wraps_primary_value_in_capsule_container(self):
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
        secondary_group = row.controls[0]
        primary_capsule = row.controls[1]
        self.assertIsInstance(secondary_group, ft.Row)
        self.assertIsInstance(primary_capsule, ft.Container)
        self.assertEqual(primary_capsule.content.value, "+1.28%")

    def test_build_fund_list_market_row_uses_light_capsule_for_primary_value(self):
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
        primary_capsule = row.controls[1]
        self.assertEqual(primary_capsule.content.color, UP)
        self.assertEqual(primary_capsule.bgcolor, ft.Colors.with_opacity(0.08, UP))
        self.assertEqual(primary_capsule.border.left.color, ft.Colors.with_opacity(0.18, UP))
        self.assertEqual(primary_capsule.border.left.width, 1)
        self.assertEqual(primary_capsule.alignment, ft.Alignment(0, 0))
        self.assertEqual(primary_capsule.border_radius, 999)
        self.assertEqual(primary_capsule.padding.left, 10)
        self.assertEqual(primary_capsule.padding.top, 6)
        self.assertEqual(primary_capsule.padding.right, 10)
        self.assertEqual(primary_capsule.padding.bottom, 6)

    def test_build_fund_list_market_row_keeps_capsule_when_primary_missing(self):
        row = FletApp._build_fund_list_market_row(
            types.SimpleNamespace(),
            {
                "secondary_label": "昨净",
                "secondary_value": "--",
                "secondary_color": VALUE_TEXT,
                "primary": "--",
                "color": SUBTEXT,
            },
        )
        primary_capsule = row.controls[1]
        self.assertIsInstance(primary_capsule, ft.Container)
        self.assertEqual(primary_capsule.content.value, "--")

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

    def test_build_fund_list_copy_button_matches_icon_toolbar_style(self):
        dummy_app = types.SimpleNamespace(open_fund_list_copy_dialog=lambda e=None: None)

        button = FletApp._build_fund_list_copy_button(dummy_app)

        self.assertIsInstance(button, ft.IconButton)
        self.assertEqual(button.icon, ft.Icons.CONTENT_COPY)
        self.assertEqual(button.icon_color, ACCENT)
        self.assertEqual(button.tooltip, "拷贝基金信息")

    def test_build_fund_list_copy_markdown_returns_markdown_table_with_expected_columns(self):
        formatter = types.SimpleNamespace()
        formatter._format_number_value = lambda raw_value, digits=2, suffix="": FletApp._format_number_value(
            formatter,
            raw_value,
            digits=digits,
            suffix=suffix,
        )
        formatter._format_pct_value = lambda raw_value, signed=True: FletApp._format_pct_value(
            formatter,
            raw_value,
            signed=signed,
        )

        markdown = FletApp._build_fund_list_copy_markdown(
            formatter,
            [
                {"name": "中欧医疗", "code": "003095", "current_nav": 1.2345, "est_pct": -0.56},
                {"name": "白酒指数", "code": "161725", "current_nav": None, "est_pct": None},
            ],
        )

        self.assertEqual(
            markdown.splitlines(),
            [
                "| 基金名称 | 代码 | 当日估值 | 估值涨跌幅 |",
                "| --- | --- | --- | --- |",
                "| 中欧医疗 | 003095 | 1.2345 | -0.56% |",
                "| 白酒指数 | 161725 | -- | -- |",
            ],
        )

    def test_open_fund_list_copy_dialog_shows_message_when_no_items(self):
        messages: list[str] = []
        dummy_app = types.SimpleNamespace(
            _fund_list_cache={"items": []},
            _sort_fund_list_items=lambda items: items,
            _show_message=lambda message: messages.append(message),
        )

        FletApp.open_fund_list_copy_dialog(dummy_app)

        self.assertEqual(messages, ["暂无可复制基金"])

    def test_open_fund_list_copy_dialog_builds_unchecked_checkboxes_in_sorted_order(self):
        dialogs: list[ft.AlertDialog] = []
        dummy_app = types.SimpleNamespace(
            _fund_list_cache={
                "items": [
                    {"name": "基金A", "code": "000001", "current_nav": 1.1111, "est_pct": 0.1},
                    {"name": "基金B", "code": "000002", "current_nav": 1.2222, "est_pct": -0.2},
                ]
            },
            _sort_fund_list_items=lambda items: list(reversed(items)),
            _open_dialog=lambda dialog: dialogs.append(dialog),
            _show_message=lambda message: None,
            _format_number_value=lambda raw_value, digits=2, suffix="": FletApp._format_number_value(
                types.SimpleNamespace(),
                raw_value,
                digits=digits,
                suffix=suffix,
            ),
            _format_pct_value=lambda raw_value, signed=True: FletApp._format_pct_value(
                types.SimpleNamespace(),
                raw_value,
                signed=signed,
            ),
        )

        FletApp.open_fund_list_copy_dialog(dummy_app)

        self.assertEqual(len(dialogs), 1)
        self.assertEqual([entry["item"]["code"] for entry in dummy_app._fund_list_copy_entries], ["000002", "000001"])
        self.assertTrue(all(entry["checkbox"].value is False for entry in dummy_app._fund_list_copy_entries))
        self.assertEqual(dialogs[0].title.value, "拷贝基金信息")

    def test_on_fund_list_copy_confirm_shows_message_when_nothing_selected(self):
        messages: list[str] = []
        dummy_app = types.SimpleNamespace(
            _fund_list_copy_entries=[
                {"item": {"code": "000001"}, "checkbox": ft.Checkbox(value=False)},
                {"item": {"code": "000002"}, "checkbox": ft.Checkbox(value=False)},
            ],
            _show_message=lambda message: messages.append(message),
            _build_fund_list_copy_markdown=lambda items: (_ for _ in ()).throw(AssertionError("不应生成 Markdown")),
            _queue_clipboard_copy=lambda text: (_ for _ in ()).throw(AssertionError("不应复制")),
            _close_dialog=lambda: (_ for _ in ()).throw(AssertionError("不应关闭弹窗")),
        )

        FletApp.on_fund_list_copy_confirm(dummy_app)

        self.assertEqual(messages, ["请至少选择一只基金"])

    def test_on_fund_list_copy_confirm_copies_markdown_and_closes_dialog(self):
        messages: list[str] = []
        copied: list[str] = []
        closed: list[bool] = []
        built_items: list[list[dict]] = []
        dummy_app = types.SimpleNamespace(
            _fund_list_copy_entries=[
                {"item": {"code": "000001", "name": "基金A"}, "checkbox": ft.Checkbox(value=True)},
                {"item": {"code": "000002", "name": "基金B"}, "checkbox": ft.Checkbox(value=False)},
            ],
            _show_message=lambda message: messages.append(message),
            _build_fund_list_copy_markdown=lambda items: built_items.append(items) or "| markdown |",
            _queue_clipboard_copy=lambda text: copied.append(text),
            _close_dialog=lambda: closed.append(True),
        )

        FletApp.on_fund_list_copy_confirm(dummy_app)

        self.assertEqual(built_items, [[{"code": "000001", "name": "基金A"}]])
        self.assertEqual(copied, ["| markdown |"])
        self.assertEqual(closed, [True])
        self.assertEqual(messages, ["已复制 1 只基金信息"])


if __name__ == "__main__":
    unittest.main()

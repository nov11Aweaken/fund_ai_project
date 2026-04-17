import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import json
import pandas as pd
import flet as ft

import main
from main import FletApp


class PageRedesignHelperTests(unittest.TestCase):
    def test_ensure_dynamic_chart_asset_copies_bundled_asset_to_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            assets_dir = base_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            bundled_asset = assets_dir / "echarts.min.js"
            bundled_asset.write_text("// bundled echarts runtime", encoding="utf-8")
            output_dir = base_dir / "charts"
            output_dir.mkdir(parents=True, exist_ok=True)

            with (
                mock.patch.object(main, "_app_dir", return_value=base_dir),
                mock.patch.object(main.requests, "get", side_effect=AssertionError("不应发起网络请求")),
            ):
                asset_path = main._ensure_dynamic_chart_asset(output_dir)
                self.assertEqual(asset_path.name, "echarts.min.js")
                self.assertTrue(asset_path.exists())
                self.assertEqual(asset_path.read_text(encoding="utf-8"), "// bundled echarts runtime")

    def test_ensure_dynamic_chart_asset_raises_when_bundled_asset_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            output_dir = base_dir / "charts"
            output_dir.mkdir(parents=True, exist_ok=True)

            with (
                mock.patch.object(main, "_app_dir", return_value=base_dir),
                mock.patch.object(main.requests, "get", side_effect=AssertionError("不应发起网络请求")),
            ):
                with self.assertRaisesRegex(ValueError, "缺少本地 ECharts 资源"):
                    main._ensure_dynamic_chart_asset(output_dir)

    def test_build_dynamic_chart_document_uses_local_echarts_script_and_full_height_layout(self):
        html = main.build_dynamic_chart_document(
            title="测试基金 (110022) 净值走势",
            option_json='{"series": [], "xAxis": []}',
            script_src="echarts.min.js",
        )

        self.assertIn('<script src="echarts.min.js"></script>', html)
        self.assertIn("height:100vh", html)
        self.assertIn("echarts.init", html)
        self.assertNotIn("assets.pyecharts.org", html)

    def test_write_dynamic_chart_html_writes_html_that_uses_local_echarts_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            charts_dir = base_dir / "charts"
            charts_dir.mkdir(parents=True, exist_ok=True)
            assets_dir = base_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            bundled_asset = assets_dir / "echarts.min.js"
            bundled_asset.write_text("// echarts runtime", encoding="utf-8")

            with (
                mock.patch.object(main, "_log_dir", return_value=base_dir),
                mock.patch.object(main, "_app_dir", return_value=base_dir),
                mock.patch.object(
                    main,
                    "build_dynamic_chart_options",
                    return_value={
                        "title": "测试基金 (110022) 净值走势",
                        "option_json": '{"series": [], "xAxis": []}',
                    },
                ),
            ):
                html_path = main.write_dynamic_chart_html(
                    {"code": "110022", "label": "测试基金 (110022)", "type": "fund"}
                )
                html = html_path.read_text(encoding="utf-8")

        self.assertIn('<script src="echarts.min.js"></script>', html)
        self.assertNotIn("assets.pyecharts.org", html)

    def test_dynamic_kline_ma_layout_contract_get_chart_html(self):
        """验证 get_chart_html()/build_dynamic_chart_document 对 MA 布局的契约（静态字符串检查）

        保留以下契约点：ma-controls-row, 7 个 data-ma-day, is-selected, ma-check。
        同时以更稳健的方式替换脆弱的旧断言：确认提示文本在标题行中，且在标题行和 ma-controls-row 之间有一个闭合的 div，表明 ma 控件在下一行。
        """
        html = main.get_chart_html("110022", "测试基金")

        # 基本元素存在性契约
        self.assertIn("ma-controls-row", html, "应包含 ma-controls-row DOM 标识")
        self.assertIn("ma-check", html, "应包含 ma-check DOM 标识")
        self.assertIn("is-selected", html, "应包含 is-selected DOM 标识")

        # 至少 7 个 data-ma-day（候选 MA 天数）
        count_data_ma = html.count("data-ma-day=")
        self.assertGreaterEqual(count_data_ma, 7, f"预期至少 7 个 data-ma-day 项，实际: {count_data_ma}")

        # 更语义化的顺序/分段断言：提示应先于 ma-controls-row，且两者之间存在闭合的 div
        hint_text = "支持缩放、悬浮提示和图片导出"
        idx_hint = html.find(hint_text)
        idx_controls = html.find("ma-controls-row")
        self.assertNotEqual(idx_hint, -1, "提示文本应存在于 HTML 中")
        self.assertNotEqual(idx_controls, -1, "ma-controls-row 应存在于 HTML 中")
        # 提示在控件之前
        self.assertLess(idx_hint, idx_controls, "提示文案应在 MA 操作区之前（标题行靠前）")
        # 在两者之间应有一个闭合 div，表示换行/结束标题行右侧容器
        between = html[idx_hint:idx_controls]
        self.assertIn("</div>", between, "提示与 MA 操作区之间应有闭合的 </div>，表明 MA 操作区为独立下一行")

    def test_dynamic_kline_ma_layout_contract_write_dynamic_chart_html(self):
        """与 get_chart_html() 相同的断言，但通过 write_dynamic_chart_html 输出文件验证契约一致性"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            charts_dir = base_dir / "charts"
            charts_dir.mkdir(parents=True, exist_ok=True)
            assets_dir = base_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            bundled_asset = assets_dir / "echarts.min.js"
            bundled_asset.write_text("// echarts runtime", encoding="utf-8")

            with (
                mock.patch.object(main, "_log_dir", return_value=base_dir),
                mock.patch.object(main, "_app_dir", return_value=base_dir),
                mock.patch.object(
                    main,
                    "build_dynamic_chart_options",
                    return_value={
                        "title": "测试基金 (110022) 净值走势",
                        "option_json": '{"series": [], "xAxis": []}',
                    },
                ),
            ):
                html_path = main.write_dynamic_chart_html({"code": "110022", "label": "测试基金 (110022)", "type": "fund"})
                html = html_path.read_text(encoding="utf-8")

        # 基本元素存在性契约
        self.assertIn("ma-controls-row", html, "应包含 ma-controls-row DOM 标识（write_dynamic_chart_html 输出）")
        self.assertIn("ma-check", html, "应包含 ma-check DOM 标识（write_dynamic_chart_html 输出）")
        self.assertIn("is-selected", html, "应包含 is-selected DOM 标识（write_dynamic_chart_html 输出）")

        # 至少 7 个 data-ma-day
        count_data_ma = html.count("data-ma-day=")
        self.assertGreaterEqual(count_data_ma, 7, f"预期至少 7 个 data-ma-day 项（write_dynamic_chart_html），实际: {count_data_ma}")

        # 顺序/分段断言
        hint_text = "支持缩放、悬浮提示和图片导出"
        idx_hint = html.find(hint_text)
        idx_controls = html.find("ma-controls-row")
        self.assertNotEqual(idx_hint, -1, "提示文本应存在于 HTML 中（write_dynamic_chart_html 输出）")
        self.assertNotEqual(idx_controls, -1, "ma-controls-row 应存在于 HTML 中（write_dynamic_chart_html 输出）")
        self.assertLess(idx_hint, idx_controls, "提示文案应在 MA 操作区之前（write_dynamic_chart_html 输出）")
        between = html[idx_hint:idx_controls]
        self.assertIn("</div>", between, "提示与 MA 操作区之间应有闭合的 </div>（write_dynamic_chart_html 输出）")

    def test_open_dynamic_kline_shows_message_when_browser_open_returns_false(self):
        messages: list[str] = []
        dummy_app = types.SimpleNamespace(
            current_target_data=lambda: {"code": "110022", "label": "测试基金 (110022)", "type": "fund"},
            _show_message=lambda message: messages.append(message),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "dynamic_fund_110022.html"
            html_path.write_text("<html></html>", encoding="utf-8")
            with (
                mock.patch.object(main, "write_dynamic_chart_html", return_value=html_path),
                mock.patch.object(main.webbrowser, "open", return_value=False),
            ):
                FletApp.open_dynamic_kline(dummy_app, None)

        self.assertEqual(messages, ["动态图打开失败：系统未找到可用的浏览器或关联程序"])

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


    def test_build_dynamic_chart_data_nan_keys_and_none_and_json_roundtrip(self):
        dates = pd.date_range("2020-01-01", periods=6, freq='D')
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        df = pd.DataFrame({"净值日期": dates, "单位净值": values})
        with mock.patch.object(main, "fetch_fund_history_data", return_value=df):
            data = main.build_dynamic_chart_data("110022", "测试基金")

        self.assertIn("ma_series", data)
        ms = data["ma_series"]
        # keys are strings for stable JSON
        self.assertTrue(all(isinstance(k, str) for k in ms.keys()))
        self.assertIn("5", ms)
        # early rolling windows should produce missing values which must be None (not NaN)
        self.assertIsNone(ms["5"][0])
        # nav values should be plain Python floats
        self.assertTrue(all(isinstance(v, float) for v in data["nav_values"]))
        # JSON round-trip preserves keys and nulls
        s = json.dumps(ms)
        loaded = json.loads(s)
        self.assertEqual(set(loaded.keys()), set(ms.keys()))
        self.assertIsNone(loaded["5"][0])

    def test_build_dynamic_chart_data_raises_on_empty_data(self):
        empty = pd.DataFrame(columns=["净值日期", "单位净值"])
        with mock.patch.object(main, "fetch_fund_history_data", return_value=empty):
            with self.assertRaisesRegex(ValueError, "动态K线图历史数据为空"):
                main.build_dynamic_chart_data("110022", "测试基金")


if __name__ == "__main__":
    unittest.main()

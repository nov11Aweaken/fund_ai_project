import tempfile
import types
import unittest
import json
from pathlib import Path
from unittest import mock

import flet as ft
import pandas as pd

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


    def test_build_dynamic_chart_data_returns_stable_json_ready_contract(self):
        dates = pd.date_range(end=pd.Timestamp("2023-01-10"), periods=10)
        df = pd.DataFrame({"净值日期": dates, "单位净值": list(range(1, 11))})

        with mock.patch.object(main, "fetch_fund_history_data", return_value=df):
            res = main.build_dynamic_chart_data("110022", "测试基金")

        self.assertEqual(res["title"], "测试基金 (110022) 净值走势")
        self.assertEqual(res["ma_candidates"], [5, 10, 20, 30, 60, 120, 250])
        self.assertEqual(res["default_ma_days"], [5, 10, 20, 250])
        self.assertEqual(len(res["dates"]), len(res["nav_values"]))
        self.assertTrue(all(isinstance(value, float) for value in res["nav_values"]))

        expected_keys = [str(day) for day in res["ma_candidates"]]
        self.assertEqual(list(res["ma_series"].keys()), expected_keys)
        for key in expected_keys:
            self.assertEqual(len(res["ma_series"][key]), len(res["dates"]))

        self.assertEqual(res["ma_series"]["5"][:4], [None, None, None, None])
        self.assertEqual(res["ma_series"]["5"][4], 3.0)
        self.assertEqual(json.loads(json.dumps(res)), res)

    def test_build_dynamic_chart_data_strips_code_suffix_from_label_name(self):
        dates = pd.date_range(end=pd.Timestamp("2023-01-10"), periods=10)
        df = pd.DataFrame({"净值日期": dates, "单位净值": list(range(1, 11))})

        with mock.patch.object(main, "fetch_fund_history_data", return_value=df):
            res = main.build_dynamic_chart_data("110022", "测试基金 (110022)")

        self.assertEqual(res["title"], "测试基金 (110022) 净值走势")

    def test_build_dynamic_chart_data_raises_when_history_is_empty(self):
        empty_df = pd.DataFrame({
            "净值日期": pd.Series(dtype="datetime64[ns]"),
            "单位净值": pd.Series(dtype="float64"),
        })

        with mock.patch.object(main, "fetch_fund_history_data", return_value=empty_df):
            with self.assertRaisesRegex(ValueError, "动态K线图历史数据为空"):
                main.build_dynamic_chart_data("110022", "测试基金")

    def test_build_dynamic_chart_data_maps_fetch_empty_error_to_dynamic_chart_empty_error(self):
        with mock.patch.object(main, "fetch_fund_history_data", side_effect=ValueError("基金历史数据为空")):
            with self.assertRaisesRegex(ValueError, "动态K线图历史数据为空"):
                main.build_dynamic_chart_data("110022", "测试基金")


if __name__ == "__main__":
    unittest.main()

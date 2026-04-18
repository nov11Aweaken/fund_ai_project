import tempfile
import types
import unittest
import json
import re
import sys
from pathlib import Path
from unittest import mock

import flet as ft
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import main
from main import FletApp


class PageRedesignHelperTests(unittest.TestCase):
    def _extract_label_block(self, html: str, day: int) -> str:
        """Extract a single <label ...>...</label> block that contains an <input ... data-ma-day='X'].
        Raises AssertionError if not found or not unique.
        """
        # extract individual <label>...</label> blocks (non-greedy) and then find the one containing the requested input
        label_pattern = re.compile(r"<label\b[^>]*>[\s\S]*?</label>", re.I)
        candidates = label_pattern.findall(html)
        # filter candidate blocks that contain the specific input[data-ma-day='{day}']
        results = [
            block for block in candidates
            if re.search(rf"<input\b[^>]*\bdata-ma-day\s*=\s*['\"]{day}['\"]", block)
        ]
        if not results:
            raise AssertionError(f"label block containing input[data-ma-day='{day}'] not found")
        if len(results) != 1:
            raise AssertionError(f"expected exactly one label block for data-ma-day='{day}', found {len(results)}")
        return results[0]

    def _assert_dynamic_kline_ma_layout_contract(self, html: str, chart_data: dict):
        """Assert the page contains the new MA controls layout and default selections.

        Checks:
        - ma-controls-row exists
        - all 7 candidate days present
        - title appears before ma-controls-row within <body> and separated by a closing tag
        - for each candidate, the enclosing <label> that contains input[data-ma-day] can be extracted
        - default days must contain checked, is-selected and ma-check markers
        - non-default candidates must NOT contain those markers
        """
        days = [5, 10, 20, 30, 60, 120, 250]
        default_days = chart_data.get("default_ma_days", [5, 10, 20, 250])

        # ma-controls-row DOM marker must be present
        self.assertIn("ma-controls-row", html)

        # all candidate data-ma-day attributes must be present somewhere (accept single or double quotes)
        for d in days:
            self.assertRegex(html, re.compile(rf"data-ma-day\s*=\s*['\"]{d}['\"]"))

        # ensure sequence in <body>: title ... </...> ... ma-controls-row
        body_m = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, re.I)
        self.assertIsNotNone(body_m)
        body = body_m.group(1)
        title = chart_data.get("title", "")
        self.assertRegex(body, re.compile(re.escape(title) + r".+?</[^>]+>.+?ma-controls-row", re.S))

        # examine each label block surrounding inputs: both default and non-default must be extractable
        for d in days:
            block = self._extract_label_block(html, d)

            if d in default_days:
                # strict: must contain checked, is-selected and ma-check
                self.assertRegex(block, r"\bchecked\b", f"day {d} must include checked")
                self.assertRegex(block, r"\bis-selected\b", f"day {d} must include is-selected")
                self.assertRegex(block, r"\bma-check\b", f"day {d} must include ma-check")
            else:
                # should not contain selection markers
                self.assertFalse(re.search(r"\bchecked\b", block) or re.search(r"\bis-selected\b", block) or re.search(r"\bma-check\b", block), f"day {d} should NOT be selected")

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
        chart_data = {
            "title": "测试基金 (110022) 净值走势",
            "dates": ["2023-01-01", "2023-01-02"],
            "nav_values": [1.0, 1.1],
            "ma_series": {"5": [None, None], "10": [None, None], "20": [None, None], "30": [None, None], "60": [None, None], "120": [None, None], "250": [None, None]},
            "ma_candidates": [5, 10, 20, 30, 60, 120, 250],
            "default_ma_days": [5, 10, 20, 250],
        }
        html = main.build_dynamic_chart_document(
            chart_data=chart_data,
            script_src="echarts.min.js",
        )

        self.assertIn('<script src="echarts.min.js"></script>', html)
        self.assertIn("height:100vh", html)
        self.assertIn("echarts.init", html)
        # accept single or double quoted data-ma-day
        self.assertRegex(html, re.compile(r"data-ma-day\s*=\s*['\"]5['\"]"))
        self.assertIn("MA250", html)
        self.assertIn("const chartData =", html)
        self.assertIn("function buildOption(selectedDays)", html)
        self.assertIn("function mergeCurrentZoom(option)", html)
        self.assertIn("chart.getOption()", html)
        self.assertNotIn("assets.pyecharts.org", html)
        # static JS assertions: ensure MA chip sync helper and DOM ops are present
        self.assertIn("function syncMaChipState", html)
        self.assertRegex(html, r"classList\.(?:add|remove)\(")
        self.assertRegex(html, r"\.ma-check\b")
        # event listener should no longer be the old simple form that only referenced renderChart
        self.assertNotIn("addEventListener('change', renderChart)", html)
        self.assertIn("addEventListener('change',", html)

    def test_build_dynamic_chart_document_outputs_ma_controls_row_and_candidates(self):
        """验证 build_dynamic_chart_document 输出新的 MA 控件行和候选项，以及默认选中标识。

        使用统一的断言 helper 以确保不同入口的一致性。
        """
        chart_data = {
            "title": "测试基金 (110022) 净值走势",
            "dates": ["2023-01-01", "2023-01-02"],
            "nav_values": [1.0, 1.1],
            "ma_series": {str(k): [None, None] for k in [5, 10, 20, 30, 60, 120, 250]},
            "ma_candidates": [5, 10, 20, 30, 60, 120, 250],
            "default_ma_days": [5, 10, 20, 250],
        }
        html = main.build_dynamic_chart_document(chart_data=chart_data, script_src="echarts.min.js")

        # 统一断言新布局契约
        self._assert_dynamic_kline_ma_layout_contract(html, chart_data)

    def test_write_dynamic_chart_html_outputs_ma_controls_row_and_defaults(self):
        chart_data = {
            "title": "测试基金 (110022) 净值走势",
            "dates": ["2023-01-01", "2023-01-02"],
            "nav_values": [1.0, 1.1],
            "ma_series": {str(k): [None, None] for k in [5, 10, 20, 30, 60, 120, 250]},
            "ma_candidates": [5, 10, 20, 30, 60, 120, 250],
            "default_ma_days": [5, 10, 20, 250],
        }
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
                    "build_dynamic_chart_data",
                    return_value=chart_data,
                ),
            ):
                html_path = main.write_dynamic_chart_html(
                    {"code": "110022", "label": "测试基金 (110022)", "type": "fund"}
                )
                html = html_path.read_text(encoding="utf-8")

        # 统一断言新布局契约
        self._assert_dynamic_kline_ma_layout_contract(html, chart_data)

    def test_get_chart_html_outputs_new_layout_contract(self):
        chart_data = {
            "title": "测试基金 (110022) 净值走势",
            "dates": ["2023-01-01", "2023-01-02"],
            "nav_values": [1.0, 1.1],
            "ma_series": {str(k): [None, None] for k in [5, 10, 20, 30, 60, 120, 250]},
            "ma_candidates": [5, 10, 20, 30, 60, 120, 250],
            "default_ma_days": [5, 10, 20, 250],
        }

        with mock.patch.object(main, "build_dynamic_chart_data", return_value=chart_data) as mock_build:
            html = main.get_chart_html("110022", "测试基金", "echarts.min.js")

        mock_build.assert_called_once_with("110022", "测试基金")
        # 统一断言新布局契约
        self._assert_dynamic_kline_ma_layout_contract(html, chart_data)
        self.assertIn('<script src="echarts.min.js"></script>', html)

    def test_build_dynamic_chart_series_keeps_nav_when_no_ma_selected(self):
        chart_data = {
            "title": "测试基金 (110022) 净值走势",
            "dates": ["2023-01-01", "2023-01-02"],
            "nav_values": [1.0, 1.1],
            "ma_series": {"5": [None, None], "10": [None, None]},
            "ma_candidates": [5, 10],
            "default_ma_days": [5],
        }

        series = main.build_dynamic_chart_series(chart_data, [])

        self.assertEqual([item["name"] for item in series], ["单位净值"])
        self.assertEqual(series[0]["data"], [1.0, 1.1])

    def test_build_dynamic_chart_option_uses_selected_ma_series(self):
        chart_data = {
            "title": "测试基金 (110022) 净值走势",
            "dates": ["2023-01-01", "2023-01-02", "2023-01-03"],
            "nav_values": [1.0, 1.1, 1.2],
            "ma_series": {
                "5": [None, None, None],
                "10": [None, None, None],
                "20": [None, None, None],
            },
            "ma_candidates": [5, 10, 20],
            "default_ma_days": [5, 10],
        }

        option = main.build_dynamic_chart_option(chart_data, [10, 5])

        self.assertEqual(option["legend"]["data"], ["单位净值", "MA10", "MA5"])
        self.assertEqual([item["name"] for item in option["series"]], ["单位净值", "MA10", "MA5"])
        self.assertEqual(option["xAxis"]["data"], chart_data["dates"])

    def test_write_dynamic_chart_html_writes_html_that_uses_local_echarts_script(self):
        chart_data = {
            "title": "测试基金 (110022) 净值走势",
            "dates": ["2023-01-01", "2023-01-02"],
            "nav_values": [1.0, 1.1],
            "ma_series": {
                "5": [None, None],
                "10": [None, None],
                "20": [None, None],
                "30": [None, None],
                "60": [None, None],
                "120": [None, None],
                "250": [None, None],
            },
            "ma_candidates": [5, 10, 20, 30, 60, 120, 250],
            "default_ma_days": [5, 10, 20, 250],
        }
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
                    "build_dynamic_chart_data",
                    return_value=chart_data,
                ),
            ):
                html_path = main.write_dynamic_chart_html(
                    {"code": "110022", "label": "测试基金 (110022)", "type": "fund"}
                )
                html = html_path.read_text(encoding="utf-8")

        self.assertIn('<script src="echarts.min.js"></script>', html)
        # accept single or double quoted data-ma-day for day 5
        self.assertRegex(html, re.compile(r"data-ma-day\s*=\s*['\"]5['\"]"))
        self.assertIn("const defaultOption =", html)
        self.assertNotIn("assets.pyecharts.org", html)

    def test_get_chart_html_uses_structured_dynamic_chart_contract(self):
        chart_data = {
            "title": "测试基金 (110022) 净值走势",
            "dates": ["2023-01-01", "2023-01-02"],
            "nav_values": [1.0, 1.1],
            "ma_series": {
                "5": [None, None],
                "10": [None, None],
                "20": [None, None],
                "30": [None, None],
                "60": [None, None],
                "120": [None, None],
                "250": [None, None],
            },
            "ma_candidates": [5, 10, 20, 30, 60, 120, 250],
            "default_ma_days": [5, 10, 20, 250],
        }

        with mock.patch.object(main, "build_dynamic_chart_data", return_value=chart_data) as mock_build:
            html = main.get_chart_html("110022", "测试基金", "echarts.min.js")

        mock_build.assert_called_once_with("110022", "测试基金")
        # accept single or double quoted data-ma-day for day 250
        self.assertRegex(html, re.compile(r"data-ma-day\s*=\s*['\"]250['\"]"))
        self.assertIn("const chartData =", html)
        self.assertIn('<script src="echarts.min.js"></script>', html)

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

    def test_build_dynamic_chart_data_uses_code_only_title_when_name_missing(self):
        dates = pd.date_range(end=pd.Timestamp("2023-01-10"), periods=10)
        df = pd.DataFrame({"净值日期": dates, "单位净值": list(range(1, 11))})

        with mock.patch.object(main, "fetch_fund_history_data", return_value=df):
            res = main.build_dynamic_chart_data("110022", "")

        self.assertEqual(res["title"], "110022 净值走势")

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

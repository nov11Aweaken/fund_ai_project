# 动态 K 线图预设 MA 多选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在外部动态图页面内部提供预设 MA 多选，支持 `5/10/20/30/60/120/250` 候选周期，默认显示 `5/10/20/250`，切换后即时重绘，关闭后不保留状态。

**Architecture:** 保持当前“Python 生成本地 HTML + 本地 ECharts 脚本渲染”的结构不变。Python 端新增结构化图表数据输出，浏览器端原生 JavaScript 根据默认选中值和复选项状态动态重建 `series`，不引入新的后端接口，也不改主界面交互。

**Tech Stack:** Python 3.13、Flet、pandas、pyecharts/ECharts、本地 HTML + 原生 JavaScript、unittest

---

## 文件结构与职责

- **Modify:** `main.py`
  - 新增结构化动态图数据准备函数
  - 调整动态图 HTML 生成函数，向页面注入候选 MA、默认选中值和前端重绘逻辑
  - 保持 `open_dynamic_kline()` 调用方式不变
- **Modify:** `tests/test_main_page_redesign.py`
  - 为动态图新增数据结构、默认选中、页面内重绘配置等回归测试
- **Reference only:** `docs/superpowers/specs/2026-04-16-dynamic-kline-ma-selection-design.md`
  - 作为实现边界与验收标准来源

> 注意：仓库当前工作区还存在与本任务无关的未提交项（如 `assets/fonts/`、`ui_prefs.json`、`main.py` 中其他改动）。执行时只提交本任务相关文件与 hunk。

### Task 1: 锁定动态图数据契约

**Files:**
- Modify: `tests/test_main_page_redesign.py`
- Modify: `main.py`
- Reference: `docs/superpowers/specs/2026-04-16-dynamic-kline-ma-selection-design.md`

- [ ] **Step 1: 写失败测试，锁定结构化动态图数据格式**

```python
def test_build_dynamic_chart_data_returns_candidates_and_default_selection(self):
    with mock.patch.object(main, "fetch_fund_history_data", return_value=sample_df):
        result = main.build_dynamic_chart_data("110022", "测试基金")

    self.assertEqual(result["ma_candidates"], [5, 10, 20, 30, 60, 120, 250])
    self.assertEqual(result["default_ma_days"], [5, 10, 20, 250])
    self.assertIn(5, result["ma_series"])
    self.assertIn(250, result["ma_series"])
```

- [ ] **Step 2: 运行测试，确认红灯**

Run: `python -m unittest discover -s tests -p "test_main_page_redesign.py" -v`  
Expected: FAIL，报错缺少 `build_dynamic_chart_data` 或返回结构不符合预期

- [ ] **Step 3: 写最小实现，补齐结构化动态图数据函数**

```python
def build_dynamic_chart_data(code: str, name: str = "") -> dict:
    # 读取历史净值
    # 计算候选 MA 序列
    # 返回 dates / nav_values / ma_series / ma_candidates / default_ma_days / title
```

- [ ] **Step 4: 再跑测试，确认转绿**

Run: `python -m unittest discover -s tests -p "test_main_page_redesign.py" -v`  
Expected: PASS，对应新测试通过

- [ ] **Step 5: 提交这一小步**

```bash
git add main.py tests/test_main_page_redesign.py
git commit -m "feat: add dynamic chart data contract" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2: 实现可测试的图表组装逻辑与页面内 MA 复选项

**Files:**
- Modify: `tests/test_main_page_redesign.py`
- Modify: `main.py`

- [ ] **Step 1: 先更新现有动态图测试清单，明确哪些旧测试需要迁移**

```python
# 需要显式调整现有：
# - test_build_dynamic_chart_document_uses_local_echarts_script_and_full_height_layout
# - test_write_dynamic_chart_html_writes_html_that_uses_local_echarts_script
```

- [ ] **Step 2: 写失败测试，锁定纯 Python `series` 组装逻辑**

```python
def test_build_dynamic_chart_series_uses_selected_ma_days_only(self):
    chart_data = sample_chart_data()
    series = main.build_dynamic_chart_series(chart_data, [5, 10, 20, 250])

    self.assertEqual([item["name"] for item in series], ["单位净值", "MA5", "MA10", "MA20", "MA250"])
```

- [ ] **Step 3: 运行测试，确认红灯**

Run: `python -m unittest discover -s tests -p "test_main_page_redesign.py" -v`  
Expected: FAIL，缺少 `build_dynamic_chart_series()` 或返回结构不符合预期

- [ ] **Step 4: 写第二个失败测试，锁定“全不选仅保留净值主线”**

```python
def test_build_dynamic_chart_series_keeps_nav_only_when_no_ma_selected(self):
    chart_data = sample_chart_data()
    series = main.build_dynamic_chart_series(chart_data, [])

    self.assertEqual([item["name"] for item in series], ["单位净值"])
```

- [ ] **Step 5: 写第三个失败测试，锁定默认首屏 option**

```python
def test_build_dynamic_chart_option_uses_default_ma_days(self):
    chart_data = sample_chart_data()
    option = main.build_dynamic_chart_option(chart_data, chart_data["default_ma_days"])

    self.assertEqual(
        [item["name"] for item in option["series"]],
        ["单位净值", "MA5", "MA10", "MA20", "MA250"],
    )
```

- [ ] **Step 6: 运行测试，确认红灯仍然准确**

Run: `python -m unittest discover -s tests -p "test_main_page_redesign.py" -v`  
Expected: FAIL，红灯准确指向 `series/option` helper 缺失

- [ ] **Step 7: 写最小实现，补齐纯 Python helper**

```python
def build_dynamic_chart_series(chart_data: dict, selected_days: list[int]) -> list[dict]:
    ...

def build_dynamic_chart_option(chart_data: dict, selected_days: list[int]) -> dict:
    ...
```

- [ ] **Step 8: 再跑测试，确认 helper 测试转绿**

Run: `python -m unittest discover -s tests -p "test_main_page_redesign.py" -v`  
Expected: PASS，新加 helper 测试通过，HTML 相关旧测试可能仍为红灯

- [ ] **Step 9: 写失败测试，锁定 HTML 默认配置和页面内重绘数据**

```python
def build_dynamic_chart_document(chart_data: dict, script_src: str) -> str:
    # 这里的测试目标应断言：
    # - HTML 内包含 ma_candidates/default_ma_days
    # - HTML 内包含 initial option JSON
    # - HTML 内包含前端重绘所需 raw data
```

- [ ] **Step 10: 实现最小 HTML 页面交互和默认首屏渲染**

```python
def build_dynamic_chart_document(chart_data: dict, script_src: str) -> str:
    # 注入 chart_data JSON
    # 注入 build_dynamic_chart_option(...) 生成的默认首屏 option JSON
    # 渲染 MA 复选项容器
    # 在原生 JS 中实现 buildSeries / rerenderChart
```

- [ ] **Step 11: 调整 `write_dynamic_chart_html()` 和 `get_chart_html()` 同步走新契约**

```python
def write_dynamic_chart_html(tgt: dict) -> Path:
    chart_data = build_dynamic_chart_data(code, name)
    html = build_dynamic_chart_document(chart_data, asset_path.name)

def get_chart_html(code: str, name: str = "", script_src: str = "echarts.min.js"):
    chart_data = build_dynamic_chart_data(code, name)
    return build_dynamic_chart_document(chart_data, script_src)
```

- [ ] **Step 12: 写失败测试，锁定“重新打开恢复默认”所依赖的初始配置**

```python
def test_write_dynamic_chart_html_uses_default_ma_days_on_each_render(self):
    html = main.write_dynamic_chart_html(target).read_text(encoding="utf-8")
    self.assertIn('"default_ma_days":[5,10,20,250]', html)
    self.assertIn('"name":"MA250"', html)
```

- [ ] **Step 13: 运行测试，确认存在合理红灯**

Run: `python -m unittest discover -s tests -p "test_main_page_redesign.py" -v`  
Expected: FAIL，红灯会准确指向 HTML 默认配置或 `get_chart_html()` 契约未同步

- [ ] **Step 14: 写最小实现，补全 JS 重建与空选择兜底逻辑**

```javascript
function buildSeries(selectedDays) {
  const normalized = selectedDays.length === 0 ? [] : selectedDays;
  return [navSeries, ...normalized.map(...)];
}
```

- [ ] **Step 15: 更新旧测试，使其断言新契约而不是旧 `option_json` 结构**

```python
# 调整现有用例，改为断言：
# - 本地脚本引用仍存在
# - HTML 包含候选周期 / 默认选中 / 初始 option
# - get_chart_html() 与 write_dynamic_chart_html() 契约一致
```

- [ ] **Step 16: 再跑测试，确认动态图专项测试转绿**

Run: `python -m unittest discover -s tests -p "test_main_page_redesign.py" -v`  
Expected: PASS，动态图相关测试全部通过

- [ ] **Step 17: 提交这一小步**

```bash
git add main.py tests/test_main_page_redesign.py
git commit -m "feat: add dynamic chart ma toggles" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3: 完整验证与收尾

**Files:**
- Verify: `main.py`
- Verify: `tests/test_main_page_redesign.py`
- Verify: `main.spec`

- [ ] **Step 1: 运行完整测试**

Run: `python -m unittest discover -s tests -v`  
Expected: OK，所有测试通过

- [ ] **Step 2: 运行语法检查**

Run: `python -m compileall main.py funds_manager.py tests`  
Expected: 无报错退出

- [ ] **Step 3: 如动态图 HTML 结构有变化，确认本地资源链路未回退**

Run:

```bash
python -c "from main import write_dynamic_chart_html; from pathlib import Path; p=Path(write_dynamic_chart_html({'code':'110022','label':'测试基金 (110022)','type':'fund'})); html=p.read_text(encoding='utf-8'); print('src=\"echarts.min.js\"' in html); print('assets.pyecharts.org' in html)"
```

Expected:

```text
True
False
```

- [ ] **Step 4: 如本次改动触及打包链路，再跑一次 PyInstaller**

Run: `python -m PyInstaller --clean .\main.spec`  
Expected: 构建成功

- [ ] **Step 5: 提交验证后的最终改动**

```bash
git add main.py tests/test_main_page_redesign.py
git commit -m "test: verify dynamic chart ma selection" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

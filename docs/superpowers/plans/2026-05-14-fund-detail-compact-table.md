# 基金详情紧凑表格卡片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将基金详情页中的“收益区间”和“均线与位置”两张卡片从分散的 tile 栅格改为紧凑三列表格行，并为方向型数值补上红绿语义。

**Architecture:** 保持详情页现有外层卡片、标题、副标题和整体布局不变，只替换这两张卡片的内容区渲染方式。实现上优先新增局部的详情页紧凑表格 helper，而不是硬改现有通用 tile helper；收益区间与均线区域继续复用既有数据来源，但会补充更适合表格渲染的字段，让 UI 层能够稳定输出“标签 / 说明 / 主值”三列结构，并精确控制红绿语义与空值回退。

**Tech Stack:** Python 3、Flet、unittest

---

## File Map

- **Modify:** `main.py`
  - 替换详情页 “收益区间” / “均线与位置” 的内容区渲染，从 tile 栅格改为紧凑表格行
  - 新增仅供详情页使用的局部 helper（如表格行 builder、表格 section builder）
  - 继续复用现有颜色常量、排版节奏和 `module_card` 风格
- **Modify:** `tests/test_main_page_redesign.py`
  - 补充详情页紧凑表格 helper 的结构、颜色、空值和顺序测试
  - 更新旧的 tile 契约测试，避免继续锁死过时布局
- **Reference:** `docs/superpowers/specs/2026-05-14-fund-detail-compact-table-design.md`

## Pre-flight Notes

- 当前环境未安装 `pytest`，统一使用 `python -m unittest discover ...`。
- 详情页已有通用 tile helper：`_create_metric_tile()`、`_build_metric_wrap_row()`；本次改动不要把它们硬改成兼容两套布局，避免把“持仓概览”也带进改动。
- `持仓概览` 必须保持现状；仅替换“收益区间”和“均线与位置”内容区。
- 红绿语义约束：
  - 收益区间主值：正红 / 负绿 / 零中性
  - 均线区偏离说明：正红 / 负绿 / 零中性
  - MA 主值：跟随偏离说明颜色
  - 估值分位主值：中性色
- 单文件验证优先使用：`python -m unittest discover -s tests -p "test_main_page_redesign.py" -v`
- 全量验证使用：
  - `python -m unittest discover -s tests -v`
  - `python -m compileall main.py funds_manager.py tests`

### Task 0: 创建隔离 worktree

**Files:**
- Modify: `N/A (git worktree only)`

- [ ] **Step 1: 记录当前工作区状态**

Run:

```bash
git status --short
git worktree list
```

Expected: 确认当前脏文件与现有 worktree，避免直接在主工作区实施。

- [ ] **Step 2: 创建实现专用 worktree**

Run:

```bash
git worktree add .worktrees/feature-fund-detail-compact-table -b feature/fund-detail-compact-table
```

Expected: 新 worktree 创建成功，用于隔离本次详情卡片表格化改动。

- [ ] **Step 3: 在新 worktree 跑基线验证**

Run:

```bash
cd .worktrees/feature-fund-detail-compact-table
python -m unittest discover -s tests -v
python -m compileall main.py funds_manager.py tests
```

Expected: 基线通过；若不通过，先记录问题再继续。

### Task 1: 先锁定详情页紧凑表格数据与结构契约

**Files:**
- Modify: `tests/test_main_page_redesign.py`
- Modify: `main.py`
- Test: `tests/test_main_page_redesign.py`

- [ ] **Step 1: 写失败测试，锁定收益区间数据继续保留四行且带红绿语义**

```python
def test_build_fund_detail_return_metrics_keeps_four_rows_with_metric_colors(self):
    dummy_app = types.SimpleNamespace(_metric_color=FletApp._metric_color)
    metrics = FletApp._build_fund_detail_return_metrics(
        dummy_app,
        {"chg3": 1.2, "chg7": -0.5, "chg15": 0.0, "chg30": None},
    )
    self.assertEqual([item["label"] for item in metrics], ["近3日", "近7日", "近15日", "近30日"])
    self.assertEqual(metrics[0]["color"], main.UP)
    self.assertEqual(metrics[1]["color"], main.DOWN)
    self.assertEqual(metrics[2]["color"], main.VALUE_TEXT)
    self.assertEqual(metrics[3]["value"], "--")
```

- [ ] **Step 2: 写失败测试，锁定均线区 `估值分位` 保持中性色而 MA 主值跟随偏离色**

```python
def test_build_fund_detail_ma_metrics_uses_neutral_percentile_and_distance_driven_ma_colors(self):
    dummy_app = types.SimpleNamespace(
        _format_pct_value=FletApp._format_pct_value,
        _format_number_value=FletApp._format_number_value,
        _metric_color=FletApp._metric_color,
    )
    metrics = FletApp._build_fund_detail_ma_metrics(
        dummy_app,
        {"percentile": 62.4, "ma5": 1.4832, "dist_ma5": 1.18, "ma20": 1.4918, "dist_ma20": -0.52},
    )
    self.assertEqual(metrics[0]["color"], main.VALUE_TEXT)
    self.assertEqual(metrics[1]["color"], main.UP)
    self.assertEqual(metrics[2]["color"], main.SUBTEXT)
```

- [ ] **Step 3: 写失败测试，锁定新的详情页表格行 helper 输出“三列行”结构**

```python
def test_build_detail_metric_table_row_returns_label_hint_value_structure(self):
    row = FletApp._build_detail_metric_table_row(
        types.SimpleNamespace(),
        {"label": "近3日", "subtitle": "短线表现", "value": "+1.82%", "color": main.UP},
    )
    self.assertIsInstance(row, ft.Row)
    self.assertEqual(len(row.controls), 3)
    self.assertEqual(row.controls[0].value, "近3日")
    self.assertEqual(row.controls[1].value, "短线表现")
    self.assertEqual(row.controls[2].value, "+1.82%")
    self.assertEqual(row.controls[2].color, main.UP)
```

- [ ] **Step 4: 写失败测试，锁定均线行在缺失偏离值时主值回退为中性色**

```python
def test_build_detail_metric_table_row_keeps_neutral_value_when_direction_missing(self):
    row = FletApp._build_detail_metric_table_row(
        types.SimpleNamespace(),
        {"label": "MA10", "subtitle": "偏离 --", "value": "1.4726", "color": main.SUBTEXT},
    )
    self.assertEqual(row.controls[2].color, main.SUBTEXT)
```

- [ ] **Step 5: 运行测试，确认先失败**

Run:

```bash
python -m unittest discover -s tests -p "test_main_page_redesign.py" -v
```

Expected: 因为详情页当前还没有紧凑表格 helper，且测试会锁定新的颜色/结构契约而失败。

- [ ] **Step 6: 写最小实现**

```python
def _build_detail_metric_table_row(self, metric: dict) -> ft.Row:
    return ft.Row(
        [
            ft.Text(metric["label"], color=SUBTEXT, size=12),
            ft.Text(metric.get("subtitle") or "", color=metric.get("subtitle_color", SUBTEXT), size=11, expand=True),
            ft.Text(metric["value"], color=metric.get("color", VALUE_TEXT), size=13, weight=ft.FontWeight.W_700, font_family=FONT_MONO),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
```

并让 `_build_fund_detail_return_metrics()`、`_build_fund_detail_ma_metrics()` 的输出字段足够支撑表格渲染与颜色规则。

- [ ] **Step 7: 再跑测试，确认转绿**

Run:

```bash
python -m unittest discover -s tests -p "test_main_page_redesign.py" -v
```

Expected: 新增 helper 与颜色语义相关测试通过。

- [ ] **Step 8: 提交 Task 1**

```bash
git add main.py tests/test_main_page_redesign.py
git commit -m "feat: add detail metric table row helpers"
```

### Task 2: 将详情页两张卡片切换到紧凑表格渲染

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main_page_redesign.py`
- Test: `tests/test_main_page_redesign.py`

- [ ] **Step 1: 写失败测试，锁定收益区间卡片不再使用旧 tile 栅格**

```python
def test_build_fund_detail_compact_section_uses_table_rows_instead_of_metric_tiles(self):
    dummy_app = types.SimpleNamespace(
        _module_card=lambda content, padding=14, expand=None: ft.Container(content=content, padding=padding, expand=expand),
        _build_detail_metric_table=lambda metrics: ft.Column([ft.Text(item["label"]) for item in metrics]),
    )
    card = FletApp._build_detail_compact_section_card(
        dummy_app,
        "收益区间",
        "聚焦短中期收益表现，便于快速判断趋势强弱。",
        [{"label": "近3日", "subtitle": "短线表现", "value": "+1.82%", "color": main.UP}],
    )
    self.assertNotIsInstance(card.content.controls[1], ft.ResponsiveRow)
    self.assertIsInstance(card.content.controls[1], ft.Column)
```

- [ ] **Step 2: 写失败测试，锁定均线区表格结构和 `估值分位` 中性色**

```python
def test_build_detail_metric_table_keeps_percentile_neutral_and_ma_rows_colored(self):
    table = FletApp._build_detail_metric_table(
        types.SimpleNamespace(),
        [
            {"label": "估值分位", "subtitle": "近历史区间", "value": "62.40%", "color": main.VALUE_TEXT},
            {"label": "MA5", "subtitle": "偏离 +1.18%", "value": "1.4832", "color": main.UP, "subtitle_color": main.UP},
        ],
    )
    self.assertEqual(table.controls[0].controls[2].color, main.VALUE_TEXT)
    self.assertEqual(table.controls[1].controls[2].color, main.UP)
```

- [ ] **Step 3: 写失败测试，锁定空值情况下表格仍稳定输出 `--`**

```python
def test_build_detail_metric_table_keeps_placeholder_rows_when_values_missing(self):
    table = FletApp._build_detail_metric_table(
        types.SimpleNamespace(),
        [{"label": "MA20", "subtitle": "偏离 --", "value": "--", "color": main.SUBTEXT}],
    )
    self.assertEqual(table.controls[0].controls[1].value, "偏离 --")
    self.assertEqual(table.controls[0].controls[2].value, "--")
```

- [ ] **Step 4: 运行测试，确认先失败**

Run:

```bash
python -m unittest discover -s tests -p "test_main_page_redesign.py" -v
```

Expected: 因当前详情页仍走 `detail_section_card(... self._build_metric_wrap_row(...))` 路线而失败。

- [ ] **Step 5: 写最小实现**

```python
returns_section = self._build_detail_compact_section_card(
    "收益区间",
    "聚焦短中期收益表现，便于快速判断趋势强弱。",
    self._build_fund_detail_return_metrics(res),
)
ma_section = self._build_detail_compact_section_card(
    "均线与位置",
    "查看估值分位与偏离均线位置，辅助判断所处区间。",
    self._build_fund_detail_ma_metrics(res),
)
```

并新增：

```python
def _build_detail_metric_table(self, metrics: list[dict]) -> ft.Column:
    return ft.Column(
        [self._build_detail_metric_table_row(metric) for metric in metrics],
        spacing=0,
    )
```

让这两张卡片改走紧凑表格渲染，而 `持仓概览` 继续保留现有 tile。

- [ ] **Step 6: 再跑测试，确认转绿**

Run:

```bash
python -m unittest discover -s tests -p "test_main_page_redesign.py" -v
```

Expected: 紧凑表格结构、颜色语义和空值稳定性测试通过。

- [ ] **Step 7: 提交 Task 2**

```bash
git add main.py tests/test_main_page_redesign.py
git commit -m "feat: render fund detail compact metric tables"
```

### Task 3: 回归验证与视觉确认

**Files:**
- Verify: `main.py`
- Verify: `tests/test_main_page_redesign.py`
- Verify: `tests/`
- Modify: `docs/superpowers/plans/2026-05-14-fund-detail-compact-table.md`

- [ ] **Step 1: 跑详情页相关测试**

Run:

```bash
python -m unittest discover -s tests -p "test_main_page_redesign.py" -v
```

Expected: 详情页重设计测试通过。

- [ ] **Step 2: 跑完整测试集**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: 全量测试通过，无新增失败。

- [ ] **Step 3: 跑语法检查**

Run:

```bash
python -m compileall main.py funds_manager.py tests
```

Expected: `main.py`、`funds_manager.py` 与 `tests/` 编译通过。

- [ ] **Step 4: 手动检查详情页视觉结果**

Run:

```bash
python main.py
```

Expected: “收益区间”和“均线与位置”比原版本更紧凑，红绿语义清晰，卡片高度没有明显增加，“持仓概览”保持原样。

- [ ] **Step 5: 提交 Task 3**

```bash
git add main.py tests/test_main_page_redesign.py docs/superpowers/plans/2026-05-14-fund-detail-compact-table.md
git commit -m "feat: tighten fund detail metric cards"
```

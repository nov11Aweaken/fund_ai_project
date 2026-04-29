# 基金列表行情指标布局重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将基金列表卡片右侧行情区调整为“昨净在左、当日估值变化在右”的单行对照布局，并弱化次指标视觉权重。

**Architecture:** 继续复用 `main.py` 中现有的行情数据装配逻辑，不改 `est_pct` 与 `prev_day_pct` 数据来源，只把右侧展示从“主值 + 次行副文本”改成“单行主次对照”。颜色语义与空值降级先在 `_build_fund_overview_metrics()` 中装配成稳定字段，再由一个轻量的右侧行情行 helper 只负责渲染顺序和层级，避免把数据判断与布局判断混在 `_update_fund_list_ui()` 里。这里“弱化一档”不通过引入新色值实现，而是通过复用现有涨跌色语义、降低字号/字重、保留标签灰色与留白来实现。最后用 `tests/test_main_fund_list_cards.py` 锁定文案、主次层级和空值布局契约。

**Tech Stack:** Python 3、Flet、unittest

---

## File Map

- **Modify:** `main.py`
  - 扩展基金列表行情指标数据结构，明确主指标与次指标所需字段
  - 新增可测试的基金列表右侧行情行 helper
  - 调整 `_update_fund_list_ui()`，改为使用新 helper 渲染右侧行情区
  - 固定次指标文案为 `昨净`，并在 UI 上弱化其视觉权重
- **Modify:** `tests/test_main_fund_list_cards.py`
  - 为新的行情行 helper 和指标数据结构补充回归测试
  - 锁定“昨净在左、主值在右、次指标弱化、零值中性”这些契约
- **Reference:** `docs/superpowers/specs/2026-04-29-fund-list-market-metric-layout-design.md`

## Pre-flight Notes

- 当前仓库工作区可能已存在未提交改动。执行本计划前，先使用独立 worktree，不要直接在当前工作区实施。
- 当前环境未安装 `pytest`，因此本计划统一使用仓库可用的 `unittest discover` 命令。
- 单文件验证优先使用：`python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v`
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

Expected: 确认当前脏文件与现有 worktree，避免直接在当前工作区实施。

- [ ] **Step 2: 创建实现专用 worktree**

Run:

```bash
git worktree add .worktrees/feature-fund-list-market-metric-layout -b feature/fund-list-market-metric-layout
```

Expected: 新 worktree 创建成功，用于隔离本次布局实现。

- [ ] **Step 3: 在新 worktree 运行基线验证**

Run:

```bash
cd .worktrees/feature-fund-list-market-metric-layout
python -m unittest discover -s tests -v
python -m compileall main.py funds_manager.py tests
```

Expected: 基线通过；若不通过，先记录基线问题，再决定是否继续。

### Task 1: 先锁定“昨净”文案与颜色语义契约

**Files:**
- Modify: `tests/test_main_fund_list_cards.py`
- Modify: `main.py`
- Test: `tests/test_main_fund_list_cards.py`

- [ ] **Step 1: 先更新现有测试，改掉仍断言旧长文案的断言**

```python
def test_build_fund_overview_metrics_returns_four_modern_metric_blocks(self):
    ...
    self.assertEqual(metrics[0]["secondary"], "昨净 +0.63%")
    self.assertEqual(metrics[0]["secondary_label"], "昨净")
    self.assertEqual(metrics[0]["secondary_value"], "+0.63%")
```

同时把当前仍断言 `3-19净值变化 +0.63%` 的旧展示契约改成新契约。

- [ ] **Step 2: 更新现有零值测试，改掉旧的组合文案断言**

```python
def test_build_fund_overview_metrics_keeps_compact_prev_metric_neutral_at_zero(self):
    ...
    self.assertEqual(metrics[0]["secondary"], "昨净 0.00%")
    self.assertEqual(metrics[0]["secondary_label"], "昨净")
```

如果计划选择继续保留 `secondary` 作为兼容字段，就必须把它的新契约一起写进测试，避免旧字段在实现时被遗漏。

- [ ] **Step 3: 写失败测试，锁定行情指标结构要包含 `昨净` 次指标文案**

```python
def test_build_fund_overview_metrics_uses_compact_prev_label_for_market_secondary(self):
    dummy_app = types.SimpleNamespace()
    metrics = FletApp._build_fund_overview_metrics(
        dummy_app,
        {"est_pct": 1.28, "prev_day_pct": -0.63},
        "3-19净值变化",
    )
    self.assertEqual(metrics[0]["secondary_label"], "昨净")
    self.assertEqual(metrics[0]["secondary_value"], "-0.63%")
```

- [ ] **Step 4: 写失败测试，锁定次指标继续复用现有涨跌色语义**

```python
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
```

颜色语义必须保持稳定；“弱化一档”由后续布局层通过字号、字重和留白去完成。

- [ ] **Step 5: 写失败测试，锁定次指标在零值时仍为中性色**

```python
def test_build_fund_overview_metrics_keeps_compact_prev_metric_neutral_at_zero(self):
    dummy_app = types.SimpleNamespace()
    metrics = FletApp._build_fund_overview_metrics(
        dummy_app,
        {"est_pct": -0.18, "prev_day_pct": 0.0},
        "上一交易日净值变化",
    )
    self.assertEqual(metrics[0]["secondary_label"], "昨净")
    self.assertEqual(metrics[0]["secondary_color"], VALUE_TEXT)
```

- [ ] **Step 6: 写失败测试，锁定 `prev_day_pct` 缺失时仍返回 `--`**

```python
def test_build_fund_overview_metrics_uses_placeholder_for_missing_prev_metric(self):
    dummy_app = types.SimpleNamespace()
    metrics = FletApp._build_fund_overview_metrics(
        dummy_app,
        {"est_pct": 1.28, "prev_day_pct": None},
        "上一交易日净值变化",
    )
    self.assertEqual(metrics[0]["secondary_label"], "昨净")
    self.assertEqual(metrics[0]["secondary_value"], "--")
```

- [ ] **Step 7: 写失败测试，锁定 `est_pct` 缺失时主值仍保持 `--`**

```python
def test_build_fund_overview_metrics_keeps_primary_placeholder_when_est_pct_missing(self):
    dummy_app = types.SimpleNamespace()
    metrics = FletApp._build_fund_overview_metrics(
        dummy_app,
        {"est_pct": None, "prev_day_pct": -0.63},
        "上一交易日净值变化",
    )
    self.assertEqual(metrics[0]["primary"], "--")
```

- [ ] **Step 8: 运行测试，确认它们先失败**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: 因当前实现仍返回旧标签文案，且尚未完全符合新的颜色语义契约而失败。

- [ ] **Step 9: 只做最小实现，让指标结构符合新契约**

```python
{
    "label": "行情",
    "primary": pct_text(item.get("est_pct")),
    "secondary": f"昨净 {pct_text(item.get('prev_day_pct'))}",
    "secondary_label": "昨净",
    "secondary_value": pct_text(item.get("prev_day_pct")),
    "secondary_color": FletApp._metric_color(self, item.get("prev_day_pct")),
}
```

只修改基金列表行情指标结构，不提前重排 UI。这里明确保留 `secondary` 作为兼容字段，避免现有调用处或旧测试在第一步就被破坏；右侧行情行 helper 不重新计算颜色。

- [ ] **Step 10: 再跑测试，确认转绿**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: Task 1 新增测试通过。

- [ ] **Step 11: 提交 Task 1**

```bash
git add main.py tests/test_main_fund_list_cards.py
git commit -m "feat: define compact previous market metric contract"
```

### Task 2: 抽出右侧行情行 helper，并完成单行对照布局

**Files:**
- Modify: `tests/test_main_fund_list_cards.py`
- Modify: `main.py`
- Test: `tests/test_main_fund_list_cards.py`

- [ ] **Step 1: 写失败测试，锁定新 helper 的左右顺序**

```python
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
```

- [ ] **Step 2: 写失败测试，锁定次指标视觉权重弱于主指标**

```python
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
```

- [ ] **Step 3: 写失败测试，锁定次指标缺失时仍保持单行布局**

```python
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
```

- [ ] **Step 4: 运行测试，确认 helper 契约先失败**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: 因 helper 尚不存在，或顺序 / 样式 / 缺失值布局不满足预期而失败。

- [ ] **Step 5: 在 `main.py` 新增最小 helper**

```python
def _build_fund_list_market_row(self, metric: dict) -> ft.Row:
    return ft.Row(
        [
            ft.Text(metric["secondary_label"], color=SUBTEXT, size=10),
            ft.Text(metric["secondary_value"], color=metric["secondary_color"], size=11),
            ft.Text(metric["primary"], color=metric["color"], size=15, weight=ft.FontWeight.W_700),
        ],
        spacing=8,
        alignment=ft.MainAxisAlignment.END,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
```

保持 helper 只负责右侧行情一行，不顺手重构其他卡片区域。

- [ ] **Step 6: 在 `_update_fund_list_ui()` 改为调用 helper**

```python
data_col = ft.Column(
    [
        self._build_fund_list_market_row(market_metric),
    ],
    spacing=2,
    horizontal_alignment=ft.CrossAxisAlignment.END,
)
```

如果仍需要保留辅助时间或其他文本，确保不把布局重新变回上下两行。

- [ ] **Step 7: 再跑测试，确认转绿**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: 新 helper 的顺序与层级测试通过。

- [ ] **Step 8: 提交 Task 2**

```bash
git add main.py tests/test_main_fund_list_cards.py
git commit -m "feat: redesign fund list market metric row"
```

### Task 3: 收尾验证，确认不破坏现有行为

**Files:**
- Verify: `tests/test_main_fund_list_cards.py`
- Verify: `tests/`
- Verify: `main.py`

- [ ] **Step 1: 跑基金列表相关测试**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: 基金列表卡片相关测试全部通过。

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

- [ ] **Step 4: 手动检查基金列表视觉结果**

Run:

```bash
python main.py
```

Expected: 基金列表中右侧行情区为单行对照布局，`昨净` 在左、主值在右，卡片高度无明显增加。

- [ ] **Step 5: 提交 Task 3**

```bash
git add main.py tests/test_main_fund_list_cards.py docs/superpowers/specs/2026-04-29-fund-list-market-metric-layout-design.md docs/superpowers/plans/2026-04-29-fund-list-market-metric-layout.md
git commit -m "feat: refine fund list market metric hierarchy"
```

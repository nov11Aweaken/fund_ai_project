# 基金列表行情区 B 版主值卡片化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将基金列表右侧行情区调整为“左侧昨净普通文本 + 右侧今日估值轻胶囊主值”的单行布局，让今日估值成为更明确的视觉焦点。

**Architecture:** 继续复用现有 `est_pct` / `prev_day_pct` 数据契约，不改 `_build_fund_overview_metrics()`，只调整 `_build_fund_list_market_row()` 的展示结构与样式层。实现重点是把主值从普通 `ft.Text` 提升为轻胶囊容器，同时让昨净继续保持普通文本辅助层；测试则锁定胶囊结构、主值颜色语义、空值稳定性和卡片高度不明显增加的视觉约束。

**Tech Stack:** Python 3、Flet、unittest

---

## File Map

- **Modify:** `main.py`
  - 调整 `_build_fund_list_market_row()`，把主值包装为轻胶囊容器
  - 复用现有涨跌颜色语义，为胶囊补充低饱和背景/轻边框样式
  - 保持 `_update_fund_list_ui()` 调用入口不变，避免扩散改动
- **Modify:** `tests/test_main_fund_list_cards.py`
  - 更新 helper 测试，锁定“左侧昨净组 + 右侧主值胶囊”结构
  - 增加主值胶囊样式与空值占位稳定性的回归测试
- **Reference:** `docs/superpowers/specs/2026-05-14-fund-list-market-metric-b-visual-design.md`

## Pre-flight Notes

- 这是在当前已实现“分组留白”基础上的增量视觉升级，不需要改动 `_build_fund_overview_metrics()`。
- 当前环境未安装 `pytest`，统一使用 `python -m unittest discover ...`。
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
git worktree add .worktrees/feature-fund-list-market-metric-b-visual -b feature/fund-list-market-metric-b-visual
```

Expected: 新 worktree 创建成功，用于隔离本次 B 版视觉升级。

- [ ] **Step 3: 在新 worktree 运行基线验证**

Run:

```bash
cd .worktrees/feature-fund-list-market-metric-b-visual
python -m unittest discover -s tests -v
python -m compileall main.py funds_manager.py tests
```

Expected: 基线通过；若不通过，先记录问题再继续。

### Task 1: 先锁定“主值轻胶囊”展示契约

**Files:**
- Modify: `tests/test_main_fund_list_cards.py`
- Modify: `main.py`
- Test: `tests/test_main_fund_list_cards.py`

- [ ] **Step 1: 写失败测试，锁定 helper 返回“左侧昨净组 + 右侧胶囊容器”结构**

```python
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
```

- [ ] **Step 2: 写失败测试，锁定胶囊保留主值颜色语义与轻样式**

```python
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
    self.assertIsNotNone(primary_capsule.bgcolor)
    self.assertIsNotNone(primary_capsule.border)
```

- [ ] **Step 3: 写失败测试，锁定 `est_pct` 缺失时仍保留胶囊结构**

```python
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
```

- [ ] **Step 4: 运行测试，确认先失败**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: 因当前 helper 仍返回普通主值文本，而不是胶囊容器而失败。

- [ ] **Step 5: 写最小实现**

```python
primary_text = ft.Text(metric["primary"], color=metric["color"], size=15, weight=ft.FontWeight.W_700)
primary_capsule = ft.Container(
    content=primary_text,
    padding=ft.Padding(10, 4, 10, 4),
    border_radius=999,
    bgcolor=_soft_metric_bg(metric["color"]),
    border=ft.Border.all(1, _soft_metric_border(metric["color"])),
)
```

并保持左侧 `昨净` 组仍是普通文本结构，不进入胶囊。

- [ ] **Step 6: 再跑测试，确认转绿**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: 主值胶囊结构与轻样式契约测试通过。

- [ ] **Step 7: 提交 Task 1**

```bash
git add main.py tests/test_main_fund_list_cards.py
git commit -m "feat: add primary capsule for fund list market row"
```

### Task 2: 回归验证与视觉确认

**Files:**
- Verify: `tests/test_main_fund_list_cards.py`
- Verify: `tests/`
- Verify: `main.py`

- [ ] **Step 1: 跑基金列表相关测试**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: 基金列表卡片相关测试通过。

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

Expected: 左侧 `昨净` 仍是普通辅助文本，右侧今日估值为轻胶囊主值，卡片高度无明显增加。

- [ ] **Step 5: 提交 Task 2**

```bash
git add main.py tests/test_main_fund_list_cards.py docs/superpowers/plans/2026-05-14-fund-list-market-metric-b-visual.md
git commit -m "feat: refine fund list market visual hierarchy"
```

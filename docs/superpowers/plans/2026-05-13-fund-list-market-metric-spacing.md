# 基金列表行情分组留白优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化基金列表右侧“昨净”与今日估值主值之间的分隔感，让“昨净组内紧凑、组间明显拉开”。

**Architecture:** 基于现有 `_build_fund_list_market_row()` 做增量调整，不改 `est_pct` / `prev_day_pct` 数据结构，也不改主值和次值的颜色语义。实现上把当前 3 个平铺文本调整为“左侧昨净小组 + 右侧主值”的两层结构，用嵌套 `ft.Row` 实现“组内紧、组间松”，并通过 `tests/test_main_fund_list_cards.py` 锁定新的间距与分组契约。

**Tech Stack:** Python 3、Flet、unittest

---

## File Map

- **Modify:** `main.py`
  - 调整 `_build_fund_list_market_row()`，将 `昨净` 标签和次值组合成左侧小组
  - 增大“昨净组”与主值之间的外部间距
  - 保持 `_update_fund_list_ui()` 调用入口不变，避免扩散改动
- **Modify:** `tests/test_main_fund_list_cards.py`
  - 更新 helper 测试，从“3 个平铺控件”改为“左组 + 主值”结构断言
  - 补充组内间距与组间间距的回归测试
- **Reference:** `docs/superpowers/specs/2026-04-29-fund-list-market-metric-layout-design.md`

## Pre-flight Notes

- 这是对已合并布局的增量细化，不需要重做旧的契约层改动。
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
git worktree add .worktrees/feature-fund-list-market-metric-spacing -b feature/fund-list-market-metric-spacing
```

Expected: 新 worktree 创建成功，用于隔离本次分组留白优化。

- [ ] **Step 3: 在新 worktree 运行基线验证**

Run:

```bash
cd .worktrees/feature-fund-list-market-metric-spacing
python -m unittest discover -s tests -v
python -m compileall main.py funds_manager.py tests
```

Expected: 基线通过；若不通过，先记录问题再继续。

### Task 1: 先锁定“分组留白”展示契约

**Files:**
- Modify: `tests/test_main_fund_list_cards.py`
- Modify: `main.py`
- Test: `tests/test_main_fund_list_cards.py`

- [ ] **Step 1: 写失败测试，锁定 helper 返回“左组 + 主值”两段结构**

```python
def test_build_fund_list_market_row_groups_secondary_metric_before_primary(self):
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
    primary = row.controls[1]
    self.assertIsInstance(secondary_group, ft.Row)
    self.assertEqual(secondary_group.controls[0].value, "昨净")
    self.assertEqual(secondary_group.controls[1].value, "-0.63%")
    self.assertEqual(primary.value, "+1.28%")
```

- [ ] **Step 2: 写失败测试，锁定组内间距小于组间间距**

```python
def test_build_fund_list_market_row_uses_larger_outer_spacing_than_inner_spacing(self):
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
    self.assertLess(secondary_group.spacing, row.spacing)
```

- [ ] **Step 3: 写失败测试，锁定缺失次值时仍保留左组结构**

```python
def test_build_fund_list_market_row_keeps_secondary_group_when_value_missing(self):
    row = FletApp._build_fund_list_market_row(
        types.SimpleNamespace(),
        {
            "secondary_label": "昨净",
            "secondary_color": VALUE_TEXT,
            "primary": "--",
            "color": SUBTEXT,
        },
    )
    secondary_group = row.controls[0]
    self.assertEqual(secondary_group.controls[1].value, "--")
    self.assertEqual(row.controls[1].value, "--")
```

- [ ] **Step 4: 运行测试，确认先失败**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: 因当前 helper 仍为 3 个平铺文本，而不是“左组 + 主值”结构而失败。

- [ ] **Step 5: 写最小实现**

```python
def _build_fund_list_market_row(self, metric: dict) -> ft.Row:
    secondary_group = ft.Row(
        [
            ft.Text(metric["secondary_label"], color=SUBTEXT, size=10),
            ft.Text(metric.get("secondary_value") or "--", color=metric["secondary_color"], size=11),
        ],
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return ft.Row(
        [
            secondary_group,
            ft.Text(metric["primary"], color=metric["color"], size=15, weight=ft.FontWeight.W_700),
        ],
        spacing=14,
        alignment=ft.MainAxisAlignment.END,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
```

实现时保持主值仍在最右侧，且不引入圆点、竖线等显性分隔元素。

- [ ] **Step 6: 再跑测试，确认转绿**

Run:

```bash
python -m unittest discover -s tests -p "test_main_fund_list_cards.py" -v
```

Expected: helper 的分组结构与间距契约测试通过。

- [ ] **Step 7: 提交 Task 1**

```bash
git add main.py tests/test_main_fund_list_cards.py
git commit -m "feat: add grouped spacing for fund list market row"
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

Expected: “昨净”标签和其数值保持紧凑，“昨净组”和主值之间有明显留白分隔，卡片高度无明显增加。

- [ ] **Step 5: 提交 Task 2**

```bash
git add main.py tests/test_main_fund_list_cards.py docs/superpowers/plans/2026-05-13-fund-list-market-metric-spacing.md
git commit -m "feat: refine fund list market spacing"
```

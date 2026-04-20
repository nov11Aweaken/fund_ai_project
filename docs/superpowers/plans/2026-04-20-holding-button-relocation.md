# 持仓按钮迁移到持仓概览卡片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将基金详情页中的“录入持仓 / 编辑持仓”入口从顶部工具栏迁移到“持仓概览”卡片标题栏右上角，改为图标+文字按钮，并保持状态同步。

**Architecture:** 在 `main.py` 中复用现有持仓入口逻辑，不改弹窗与保存流程，只调整按钮控件类型、挂载位置和卡片头部布局。为保证可测试性，抽出轻量的详情顶部行与详情卡片构造 helper，用 `tests/test_main_page_redesign.py` 锁定按钮状态、位置和刷新契约。

**Tech Stack:** Python 3、Flet、unittest

---

## File Map

- **Modify:** `main.py`
  - 将 `btn_detail_holding_action` 从 `ft.IconButton` 调整为图标+文字按钮
  - 扩展 `_detail_holding_action_config()` 返回 `label`
  - 扩展 `_refresh_detail_holding_action()` 同步 `label / icon / tooltip / style`
  - 抽出可测试的详情顶部行 helper 与详情卡片 helper
  - 将持仓按钮从顶部工具栏移入“持仓概览”卡片头部
- **Modify:** `tests/test_main_page_redesign.py`
  - 为按钮配置、按钮刷新、顶部行布局、卡片头部动作区新增/更新回归测试
- **Reference:** `docs/superpowers/specs/2026-04-20-holding-button-relocation-design.md`

## Pre-flight Notes

- 当前仓库 `master` 工作区可能存在未提交改动。执行本计划前，先使用 **独立 worktree**，不要直接在当前工作区实施。
- 单文件验证优先使用：`python -m unittest discover -s tests -p test_main_page_redesign.py -v`
- 全量验证使用：
  - `python -m unittest discover -s tests -v`
  - `python -m compileall main.py funds_manager.py tests`

### Task 0: 创建隔离 worktree

**Files:**
- Modify: `N/A (git worktree only)`

- [ ] **Step 1: 确认当前工作区状态**

Run:

```bash
git status --short
git worktree list
```

Expected: 记录当前脏文件，确认要从 `master` 派生新 worktree。

- [ ] **Step 2: 创建实现专用 worktree**

Run:

```bash
git worktree add .worktrees/feature-holding-button-relocation -b feature/holding-button-relocation
```

Expected: 新 worktree 创建成功，不污染当前工作区。

- [ ] **Step 3: 在新 worktree 运行基线验证**

Run:

```bash
cd .worktrees/feature-holding-button-relocation
python -m unittest discover -s tests -v
python -m compileall main.py funds_manager.py tests
```

Expected: 基线通过；若基线不通过，先记录并停止实施。

### Task 1: 锁定持仓按钮状态契约

**Files:**
- Modify: `tests/test_main_page_redesign.py`
- Modify: `main.py`
- Test: `tests/test_main_page_redesign.py`

- [ ] **Step 1: 先写失败测试，锁定按钮配置新增 `label` 字段**

```python
def test_detail_holding_action_config_uses_add_label_without_holding(self):
    dummy_app = types.SimpleNamespace(_get_fund_config_item=lambda code: {"code": code})
    config = FletApp._detail_holding_action_config(dummy_app, "110022")
    self.assertEqual(config["label"], "录入持仓")


def test_detail_holding_action_config_uses_edit_label_with_holding(self):
    dummy_app = types.SimpleNamespace(
        _get_fund_config_item=lambda code: {"code": code, "holding": {"units": 10, "cost_amount": 12}}
    )
    config = FletApp._detail_holding_action_config(dummy_app, "110022")
    self.assertEqual(config["label"], "编辑持仓")
```

- [ ] **Step 2: 写失败测试，锁定按钮刷新要同步文案 / 图标 / tooltip / 样式**

```python
def test_refresh_detail_holding_action_updates_button_label_icon_tooltip_and_bgcolor(self):
    button = ft.Button("旧文案", icon=ft.Icons.ADD_CARD)
    dummy_app = types.SimpleNamespace(
        btn_detail_holding_action=button,
        current_target_data=lambda: {"code": "110022"},
        _detail_holding_action_config=lambda code: {
            "label": "编辑持仓",
            "icon": ft.Icons.EDIT_NOTE,
            "tooltip": "编辑持仓",
            "bgcolor": "#102196F3",
        },
    )
    FletApp._refresh_detail_holding_action(dummy_app)
    self.assertEqual(button.text, "编辑持仓")
    self.assertEqual(button.icon, ft.Icons.EDIT_NOTE)
    self.assertEqual(button.tooltip, "编辑持仓")
    self.assertEqual(
        button.style.bgcolor[ft.ControlState.DEFAULT],
        "#102196F3",
    )
```

- [ ] **Step 3: 运行测试，确认它们先失败**

Run:

```bash
python -m unittest discover -s tests -p test_main_page_redesign.py -v
```

Expected: 新增测试因缺少 `label` 或按钮刷新不支持文本按钮而失败。

- [ ] **Step 4: 最小实现按钮配置与刷新契约**

```python
def _detail_holding_action_config(self, code: str | None) -> dict:
    return {
        "label": "编辑持仓" if has_holding else "录入持仓",
        "icon": ft.Icons.EDIT_NOTE if has_holding else ft.Icons.ADD_CARD,
        "tooltip": "编辑持仓" if has_holding else "录入持仓",
        "bgcolor": "#102196F3" if has_holding else "#0F2196F3",
    }


def _refresh_detail_holding_action(self):
    button.text = config["label"]
    button.icon = config["icon"]
    button.tooltip = config["tooltip"]
```

同时把 `btn_detail_holding_action` 从 `ft.IconButton(...)` 调整为带 `text` 和 `icon` 的按钮控件。

- [ ] **Step 5: 再跑测试，确认转绿**

Run:

```bash
python -m unittest discover -s tests -p test_main_page_redesign.py -v
```

Expected: Task 1 新增测试通过。

- [ ] **Step 6: 提交 Task 1**

```bash
git add main.py tests/test_main_page_redesign.py
git commit -m "feat: sync holding action label and style"
```

### Task 2: 抽出可测试的详情布局 helper，并迁移按钮位置

**Files:**
- Modify: `tests/test_main_page_redesign.py`
- Modify: `main.py`
- Test: `tests/test_main_page_redesign.py`

- [ ] **Step 1: 先写失败测试，锁定顶部行不再包含持仓按钮**

```python
def test_build_detail_top_row_uses_refresh_only_action_group(self):
    refresh = ft.IconButton(ft.Icons.REFRESH)
    dropdown = ft.Container()
    dummy_app = types.SimpleNamespace(dd_target=dropdown, btn_refresh=refresh)
    row = FletApp._build_detail_top_row(dummy_app)
    actions = row.controls[1]
    self.assertEqual(actions.controls, [refresh])
```

- [ ] **Step 2: 写失败测试，锁定详情卡片头部支持 action 区**

```python
def test_build_detail_section_card_places_action_in_header(self):
    action = ft.Button("录入持仓", icon=ft.Icons.ADD_CARD)
    dummy_app = types.SimpleNamespace(
        _module_card=lambda content, padding=14, expand=None: ft.Container(content=content, padding=padding, expand=expand),
        _build_metric_wrap_row=lambda controls: ft.ResponsiveRow(controls),
    )
    card = FletApp._build_detail_section_card(dummy_app, "持仓概览", "说明", [], action=action)
    header = card.content.controls[0]
    self.assertIs(header.controls[1], action)
```

- [ ] **Step 3: 运行测试，确认它们先失败**

Run:

```bash
python -m unittest discover -s tests -p test_main_page_redesign.py -v
```

Expected: 因 helper 尚不存在或布局不符合预期而失败。

- [ ] **Step 4: 最小实现顶部行 helper 和卡片 helper**

```python
def _build_detail_top_row(self) -> ft.Row:
    return ft.Row(
        [
            ft.Container(content=self.dd_target, expand=True),
            ft.Row([self.btn_refresh], spacing=8),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _build_detail_section_card(self, title: str, subtitle: str, tiles: list[dict], action: ft.Control | None = None):
    header_left = ft.Column([...], spacing=4, expand=True)
    header = ft.Row([header_left, action] if action is not None else [header_left], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
```

- [ ] **Step 5: 在详情页组装里使用新 helper**

```python
top_row = self._build_detail_top_row()
holding_section = self._build_detail_section_card(
    "持仓概览",
    "录入持仓后自动计算市值、当日盈亏与累计盈亏。",
    self.detail_holding_tiles,
    action=self.btn_detail_holding_action,
)
returns_section = self._build_detail_section_card(...)
ma_section = self._build_detail_section_card(...)
```

Expected: 顶部只保留目标选择 + 刷新；持仓按钮进入持仓概览卡片头部右上角。

- [ ] **Step 6: 再跑测试，确认转绿**

Run:

```bash
python -m unittest discover -s tests -p test_main_page_redesign.py -v
```

Expected: Task 2 新增布局测试通过。

- [ ] **Step 7: 提交 Task 2**

```bash
git add main.py tests/test_main_page_redesign.py
git commit -m "feat: move holding action into holding overview card"
```

### Task 3: 锁定保存与缓存回放链路的回归

**Files:**
- Modify: `tests/test_main_page_redesign.py`
- Modify: `main.py` (only if回归测试暴露缺口)
- Test: `tests/test_main_page_redesign.py`

- [ ] **Step 1: 补失败测试，覆盖状态切换链路**

```python
def test_on_holding_save_confirm_refreshes_card_button_to_edit_state(self):
    button = ft.Button("录入持仓", icon=ft.Icons.ADD_CARD)
    dummy_app = types.SimpleNamespace(
        btn_detail_holding_action=button,
        _pending_holding_target={"code": "110022", "name": "测试基金"},
        _read_holding_form_values=lambda: ("100", "200"),
        _show_holding_form_error=lambda message: None,
        _show_message=lambda message: None,
        _close_dialog=lambda: None,
        _safe_run_task=lambda fn, *args: None,
        funds=[],
        active_tab="fund",
        current_target_data=lambda: {"code": "110022", "label": "测试基金 (110022)", "type": "fund"},
        _apply_holding_to_cached_items=lambda code, holding: ([], ""),
        _refresh_detail_holding_action=lambda: FletApp._refresh_detail_holding_action(dummy_app),
        _detail_holding_action_config=lambda code: {"label": "编辑持仓", "icon": ft.Icons.EDIT_NOTE, "tooltip": "编辑持仓", "bgcolor": "#102196F3"},
        refresh_fund_list=lambda: None,
        manual_refresh=lambda: None,
    )
    with mock.patch.object(main, "update_fund_holding_and_save", return_value=[{"code": "110022", "holding": {"units": 100.0, "cost_amount": 200.0}}]):
        FletApp.on_holding_save_confirm(dummy_app)
    self.assertEqual(button.text, "编辑持仓")
```

- [ ] **Step 2: 再写失败测试，覆盖缓存回放后按钮状态不回退**

```python
def test_apply_cached_state_keeps_card_button_state_synced(self):
    button = ft.Button("录入持仓", icon=ft.Icons.ADD_CARD)
    dummy_app = types.SimpleNamespace(
        btn_detail_holding_action=button,
        _cache={"110022-fund": {"detail_holding_raw": {}, "detail_return_raw": {}, "detail_ma_raw": {}, "updated_at": "now"}},
        current_target_data=lambda: {"code": "110022"},
        _detail_holding_action_config=lambda code: {"label": "编辑持仓", "icon": ft.Icons.EDIT_NOTE, "tooltip": "编辑持仓", "bgcolor": "#102196F3"},
        _refresh_detail_holding_action=lambda: FletApp._refresh_detail_holding_action(dummy_app),
        _apply_metric_group=lambda *args, **kwargs: None,
        detail_holding_tiles=[],
        detail_return_tiles=[],
        detail_ma_tiles=[],
        _build_fund_detail_holding_metrics=lambda raw: [],
        _build_fund_detail_return_metrics=lambda raw: [],
        _build_fund_detail_ma_metrics=lambda raw: [],
        txt_header_title=types.SimpleNamespace(value=""),
        txt_header_time=types.SimpleNamespace(value=""),
        txt_price=types.SimpleNamespace(value=""),
        txt_change=types.SimpleNamespace(value=""),
        chart_img=types.SimpleNamespace(src=b"", visible=False),
        chart_loading_hint=types.SimpleNamespace(visible=False),
        chart_card=types.SimpleNamespace(update=lambda: None),
        page=types.SimpleNamespace(update=lambda: None),
    )
    FletApp._apply_cached_state(dummy_app, "110022-fund")
    self.assertEqual(button.text, "编辑持仓")
```

- [ ] **Step 3: 运行测试，确认它们先失败（如果当前实现仍有缺口）**

Run:

```bash
python -m unittest discover -s tests -p test_main_page_redesign.py -v
```

Expected: 若保存成功链路或缓存回放链路遗漏按钮刷新，会在这里暴露。

- [ ] **Step 4: 做最小修复**

只在必要时补齐 `on_holding_save_confirm()`、`_apply_cached_state()` 或相关刷新路径中的按钮同步调用，不做额外 UI 调整。

- [ ] **Step 5: 运行详情页测试与全量验证**

Run:

```bash
python -m unittest discover -s tests -p test_main_page_redesign.py -v
python -m unittest discover -s tests -v
python -m compileall main.py funds_manager.py tests
```

Expected: 全部通过。

- [ ] **Step 6: 人工验收**

Run:

```bash
python main.py
```

人工确认：

1. 顶部工具栏只剩目标基金选择和刷新按钮；
2. “持仓概览”卡片右上角出现图标+文字按钮；
3. 无持仓显示“录入持仓”，录入后变成“编辑持仓”；
4. 点击卡片内按钮仍打开原持仓弹窗；
5. 卡片窄宽度下允许头部换行，但按钮不掉进指标区。

- [ ] **Step 7: 提交 Task 3**

```bash
git add main.py tests/test_main_page_redesign.py
git commit -m "test: lock holding action relocation regressions"
```

### Task 4: 收尾与集成

**Files:**
- Modify: `N/A (git metadata only)`

- [ ] **Step 1: 检查只包含本计划相关改动**

Run:

```bash
git status --short
git --no-pager diff --stat
```

Expected: 只包含 `main.py` 和 `tests/test_main_page_redesign.py` 的相关改动。

- [ ] **Step 2: 汇总提交并准备发起 review**

Run:

```bash
git --no-pager log --oneline --decorate -5
```

Expected: 能清楚看到本计划对应的分步提交。

- [ ] **Step 3: 推送 worktree 分支**

```bash
git push -u origin feature/holding-button-relocation
```

- [ ] **Step 4: 请求代码审查**

使用 `@superpowers:requesting-code-review`，基于本计划任务边界发起 review。

# 动态 K 线图 MA 布局优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让动态图页面中的 7 个固定 MA 候选稳定可见，并把 MA 选择区调整为标题下方的独立胶囊行，优化选中态但不破坏现有重绘与缩放保持逻辑。

**Architecture:** 保持当前“Python 生成本地 HTML + 本地 ECharts + 页面内 JavaScript 重绘”的结构不变，只调整 `build_dynamic_chart_document()` 输出的 DOM/CSS/JS 组织。测试继续集中在 `tests/test_main_page_redesign.py`，通过结构化 HTML 断言锁定布局、状态标记和入口链路。

**Tech Stack:** Python, unittest, Flet, ECharts, 内嵌 HTML/CSS/JavaScript

---

## File Map

- **Modify:** `main.py`
  - `build_dynamic_chart_document()`：把 MA 区从右上角工具栏拆到标题下方独立一行，增加稳定 DOM 标识、选中态样式和勾选标记
  - 保持现有 `build_dynamic_chart_data()` / `build_dynamic_chart_series()` / `build_dynamic_chart_option()` 契约不变
  - 保持 `get_chart_html()` / `write_dynamic_chart_html()` 继续走结构化数据链路
- **Modify:** `tests/test_main_page_redesign.py`
  - 增加/更新动态图页面布局回归测试
  - 锁定 7 个 MA 候选、标题/提示/MA 分层结构、选中态类名/标记、入口链路与本地 ECharts 脚本

## Task 1: 锁定布局优化回归测试

**Files:**
- Modify: `tests/test_main_page_redesign.py`
- Reference: `main.py`

- [ ] **Step 1: 为新布局写失败测试**

  在 `PageRedesignHelperTests` 中新增或更新测试，至少覆盖：
  - `build_dynamic_chart_document()` 输出独立的 `ma-controls-row`
  - 7 个固定候选 `data-ma-day='5'...'250'` 全部存在
  - 默认选中项输出稳定类名/标记，例如 `is-selected`、`ma-check`
  - 标题行与提示文案不再和 MA 胶囊混在同一个右侧容器里
  - `get_chart_html()` / `write_dynamic_chart_html()` 继续输出新布局的关键 DOM

  示例断言结构：

  ```python
  self.assertIn("class='ma-controls-row'", html)
  self.assertIn("data-ma-day='30'", html)
  self.assertIn("is-selected", html)
  self.assertIn("ma-check", html)
  ```

- [ ] **Step 2: 运行单测确认当前实现失败**

  Run:

  ```powershell
  Set-Location E:\ai_project\.worktrees\feature-dynamic-kline-ma-selection
  python -m unittest discover -s tests -p test_main_page_redesign.py -v
  ```

  Expected: 与新布局断言相关的 1 个或多个测试失败，因为当前 HTML 仍是右上角工具区结构。

- [ ] **Step 3: 提交失败测试**

  ```powershell
  Set-Location E:\ai_project\.worktrees\feature-dynamic-kline-ma-selection
  git add tests\test_main_page_redesign.py
  git commit -m "Add MA layout polish regression tests" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

## Task 2: 实现标题下方独立 MA 胶囊行

**Files:**
- Modify: `main.py`
- Test: `tests/test_main_page_redesign.py`

- [ ] **Step 1: 重组 `build_dynamic_chart_document()` 的顶部 DOM**

  把现有顶部区域改成两层：
  1. `title-bar`（标题 + 右侧提示）
  2. `ma-controls-row`（独立 MA 胶囊行）

  关键点：
  - MA 胶囊不再嵌在当前 `toolbar-right` 里
  - 7 个候选周期按固定顺序输出
  - 每个候选保留 `data-ma-day="<周期>"`

- [ ] **Step 2: 实现新的胶囊样式与选中态标记**

  在内嵌 CSS/HTML 中加入：
  - 独立 MA 行的换行布局
  - 胶囊默认态样式
  - 选中态 `is-selected`
  - 勾选标记节点 `ma-check`

  建议实现方向：

  ```html
  <label class="ma-chip is-selected">
    <input type="checkbox" ... checked>
    <span class="ma-check">✓</span>
    <span>MA5</span>
  </label>
  ```

- [ ] **Step 3: 保持现有重绘与缩放逻辑不回退**

  修改 HTML/JS 时确认以下逻辑不变：
  - `renderChart()` 仍基于当前勾选状态重建 `series`
  - `mergeCurrentZoom()` 仍在重绘前合并当前缩放范围
  - 全部 MA 取消时仍保留单位净值主线
  - 不引入 localStorage/cookies/URL 参数保存状态

- [ ] **Step 4: 运行动态图相关单测确认通过**

  Run:

  ```powershell
  Set-Location E:\ai_project\.worktrees\feature-dynamic-kline-ma-selection
  python -m unittest discover -s tests -p test_main_page_redesign.py -v
  ```

  Expected: `test_main_page_redesign.py` 全部通过，且新布局断言转绿。

- [ ] **Step 5: 提交实现**

  ```powershell
  Set-Location E:\ai_project\.worktrees\feature-dynamic-kline-ma-selection
  git add main.py tests\test_main_page_redesign.py
  git commit -m "Polish dynamic chart MA layout" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

## Task 3: 全量验证与收尾

**Files:**
- Modify: `main.py` (only if Task 2 verification暴露问题)
- Modify: `tests/test_main_page_redesign.py` (only if Task 2 verification暴露问题)

- [ ] **Step 1: 运行完整单测**

  Run:

  ```powershell
  Set-Location E:\ai_project\.worktrees\feature-dynamic-kline-ma-selection
  python -m unittest discover -s tests -v
  ```

  Expected: 全部测试通过，无新增回归。

- [ ] **Step 2: 运行语法检查**

  Run:

  ```powershell
  Set-Location E:\ai_project\.worktrees\feature-dynamic-kline-ma-selection
  python -m compileall main.py funds_manager.py tests
  ```

  Expected: 编译通过，无语法错误。

- [ ] **Step 3: 检查工作树差异**

  Run:

  ```powershell
  Set-Location E:\ai_project\.worktrees\feature-dynamic-kline-ma-selection
  git status --short
  git --no-pager diff -- main.py tests\test_main_page_redesign.py
  ```

  Expected:
  - 只包含本次 MA 布局优化相关改动
  - 没有引入无关文件变更

- [ ] **Step 4: 做一次页面宽度人工验收**

  在环境允许时，打开外部动态图页面，至少确认两种宽度场景：
  - 常规桌面宽度：7 个 MA 胶囊完整可见，无横向滚动
  - 窄窗口宽度（接近或低于 480px）：MA 胶囊自动换行，仍可点击，提示文案与标题不挤压到同一行

  Expected:
  - 视觉层级符合 spec
  - 不出现“只剩默认 4 个 MA 可见”的回退
  - 勾选任意 MA 后仍即时重绘且保持当前缩放视窗

- [ ] **Step 5: 如验证阶段做了额外修正，提交收尾 commit**

  ```powershell
  Set-Location E:\ai_project\.worktrees\feature-dynamic-kline-ma-selection
  git add main.py tests\test_main_page_redesign.py
  git commit -m "Verify MA layout polish" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  ```

  如果没有新增修正，本步骤跳过。

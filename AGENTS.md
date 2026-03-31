# AGENTS.md

## 目的
- 本仓库是一个基于 Flet 的 Windows 桌面 Python 应用。
- 本文件用于给各类智能编码代理提供安全、最小化、贴合仓库实际情况的操作指导。
- 优先遵循仓库现有约定，不要套用泛化的框架建议。

## 交流与输出语言
- 本项目中，代理与用户的回复统一使用中文。
- 本项目中，代理编写的 Markdown 文档统一使用中文。
- 日志、提示文案、注释等如果修改了现有中文区域，优先保持中文语境一致。
- 仅在必须保留的命令、代码标识符、库名、协议字段中使用英文。

## 项目概览
- 主入口文件：`main.py`
- 基金配置与数据规范化逻辑：`funds_manager.py`
- 测试目录：`tests/`
- 源码运行时配置文件：仓库根目录下的 `funds.json`
- 打包运行时配置文件：与 `main.exe` 同级目录下的 `funds.json`
- 打包规格文件：`main.spec`
- Windows 一键打包脚本：`build_exe.bat`

## 环境说明
- 主要运行平台是 Windows。
- 本地可能存在虚拟环境目录 `.venv/`。
- `build/` 与 `dist/` 中可能已有构建产物；除非任务明确与打包有关，否则不要编辑生成文件。
- `.github/` 虽然在 `.gitignore` 中被排除，但仓库本地确实存在，应将其视为有效项目规则来源。

## 安装与运行命令
- 安装依赖：`python -m pip install -r requirements.txt`
- 启动应用：`python main.py`
- 快速语法检查：`python -m compileall main.py funds_manager.py tests`

## 测试命令
- 运行完整 `unittest` 测试：`python -m unittest discover -s tests -v`
- 使用 `pytest` 运行完整测试：`python -m pytest tests -q`
- 运行单个测试文件：`python -m pytest tests/test_funds_manager.py -q`
- 运行单个测试类：`python -m pytest tests/test_funds_manager.py::FundsManagerTests -q`
- 运行单个测试方法：`python -m pytest tests/test_funds_manager.py::FundsManagerTests::test_add_fund_and_save_preserves_existing_holding -q`

## 单测运行注意事项
- 在本仓库中，运行单个测试时优先使用 `pytest`。
- `python -m unittest discover -s tests -v` 已验证可用于完整测试集。
- 类似 `python -m unittest tests.test_funds_manager...` 这样的点路径单测命令当前不可用，因为 `tests/` 不是包。
- 如果只想跑一个 `unittest.TestCase` 风格的方法，请使用 `pytest` 的 node id。

## 构建与打包命令
- 直接按 spec 打包：`pyinstaller main.spec`
- 使用模块方式打包：`python -m PyInstaller --clean .\main.spec`
- 使用交互式脚本打包：`build_exe.bat`
- 打包后的主程序预期输出：`dist/main.exe`

## 验证建议
- 纯 Python 逻辑修改后，至少运行：`python -m unittest discover -s tests -v`
- UI 相关改动后，如环境允许，额外运行：`python main.py`
- 打包相关改动后，运行：`python -m PyInstaller --clean .\main.spec`
- 如果只是快速确认语法，优先使用：`python -m compileall main.py funds_manager.py tests`

## 来自 Copilot 规则的仓库约束
- 将 `.github/copilot-instructions.md` 视为当前项目有效规则。
- 本项目是基于 Flet 的 Python 桌面应用。
- 主入口固定为 `main.py`。
- 市场指数页面只允许使用 AkShare 的 Eastmoney 指数数据。
- 市场指数项由 `MARKET_INDEX_CONFIGS` 配置，字段包括 `code`、`name`、`category`。
- 市场指数匹配逻辑必须保持“代码优先”。
- 不要重新引入该页面对 Sina 的回退逻辑。

## 目录与职责约定
- 小而可复用的基金配置、规范化、持仓辅助逻辑放在 `funds_manager.py`。
- 应用编排、数据抓取、Flet UI 组合逻辑默认放在 `main.py`，除非确实需要新的抽象。
- 新测试放在 `tests/` 下，并优先保持现有 `unittest.TestCase` 风格。

## Cursor 与其他规则文件
- 当前仓库中未发现 `.cursorrules`。
- 当前仓库中未发现 `.cursor/rules/` 目录规则文件。
- 如果后续新增这些规则文件，代理应将其与本文件、`.github/copilot-instructions.md` 一并遵循。

## 导入规范
- 保持当前文件中的导入分组方式。
- 标准库导入放在最前。
- 第三方库导入放在中间。
- 本地模块导入放在最后。
- 不同导入组之间保留一个空行。
- 标准库尽量一行一个模块，除非当前文件已有更清晰的既有写法。
- 保留仓库已使用的别名，例如 `import flet as ft`、`import pyecharts.options as opts`。

## 格式规范
- 优先贴合仓库现有 Python 风格，不要引入新的格式化风格。
- 使用 4 个空格缩进。
- 行宽以可读性优先；本项目的 UI 构造代码允许适度偏长，但不要为了硬换行破坏结构可读性。
- 用空行分隔逻辑块，尤其是辅助函数、网络逻辑、UI 片段之间。
- 注释保持简短，只在解释意图、回退行为、Flet 或 PyInstaller 细节时添加。

## 类型规范
- 优先使用仓库已存在的内置泛型写法，例如 `list[dict]`、`dict[str, str]`。
- 新增函数在合适时补充类型标注。
- 保持轻量级类型风格，不要引入复杂类型体系。
- 可选值使用 `| None`。
- 如果函数返回灵活字典结构，键名必须稳定，并与调用处或测试保持一致。

## 命名规范
- 函数、方法、变量、模块级辅助函数使用 `snake_case`。
- 模块级常量使用 `UPPER_CASE`，例如颜色、请求头、刷新时间常量。
- 类名使用 `PascalCase`，例如 `FletApp`、`FundsManagerTests`。
- 非公开辅助函数或方法可使用前导下划线。
- 命名尽量贴合领域语义，优先沿用已有术语：`fund`、`holding`、`market`、`nav`、`pct`、`config_path`。

## 错误处理
- 用户输入校验、数据格式异常、解析失败等情况优先抛出 `ValueError`。
- 包装底层异常时保留异常链，优先使用 `raise ... from exc`。
- 对 UI 与数据抓取流程中有运维价值的错误，使用 `LOGGER` 记录。
- 当应用需要保持可用时，优先软失败，例如返回默认值、部分结果、占位数据。
- 不要无声吞掉异常，除非该回退行为是明确设计且上下文足够清晰。

## 日志规范
- 运行期诊断日志使用 `main.py` 中已初始化的 `LOGGER`。
- 如果修改周边代码已使用中文日志，新增日志也保持简洁中文。
- 避免高频、逐帧、逐次渲染的噪声日志。

## 配置与数据处理
- 配置文件定位以 `_config_path()` 的行为为准。
- 保持对 `funds.json` 与 `fund.json` 的兼容回退支持。
- 写入配置时保持 UTF-8 编码，并使用 `ensure_ascii=False`。
- 保持现有配置结构：`{"funds": [...]}`。
- 基金项规范化优先复用 `funds_manager.py` 中的辅助函数，不要在别处重复实现。

## 网络与市场数据
- 优先复用现有请求头常量和请求模式，不要随意新增零散请求实现。
- 调整 Eastmoney 请求时，复用当前的重试逻辑与代理绕过逻辑。
- 市场指数抓取逻辑要保持“代码优先”和“分类感知”。
- 外部数据缺失或格式异常时，优先显式校验并给出明确 `ValueError`。

## Flet UI 约定
- 保持 `main.py` 中已形成的界面风格与结构语言。
- 优先复用已有的颜色、字体、间距、卡片表面等常量。
- 对重复出现的卡片、指标块、行布局，优先使用已有辅助构造方法，避免大段复制。
- 保持 `ft.ResponsiveRow`、`col={...}`、`expand=True` 等现有响应式模式。
- 基金详情、基金列表、市场页签之间的状态与行为要与现有逻辑一致。

## 状态管理
- 优先沿用 `FletApp` 上直接持有实例属性的方式，不要额外引入状态管理框架。
- 涉及缓存和界面状态联动时，确保二者同步更新。
- 修改刷新流程时，保留当前的刷新中标记、待刷新标记和防重入保护。

## 测试风格
- 现有测试使用 `unittest.TestCase`，新增测试默认保持一致。
- 尽量编写聚焦辅助函数和数据整理逻辑的测试，而不是重度驱动整个 Flet UI。
- 优先使用 `types.SimpleNamespace`、临时目录、直接方法调用等可预测、低依赖的测试方式。
- 修改返回结构、展示格式、配置写入行为时，应补充或更新对应回归测试。

## 代理改动策略
- 始终做最小且正确的修改。
- 非必要不要进行大范围重构。
- 不要为了迎合抽象层次而随意移动代码文件。
- 未经明确要求，不要引入 Black、Ruff、isort、mypy、pre-commit 等新工具。
- 正常功能开发不要修改 `build/` 或 `dist/` 中的生成文件。

## 处理市场数据时的额外规则
- 任何市场页相关改动都要再次核对：该页面仅允许 Eastmoney 指数数据。
- 不要把 Sina 回退逻辑重新带回市场指数页。
- 支持的市场指数集合应继续由 `MARKET_INDEX_CONFIGS` 驱动。

## 处理基金数据时的额外规则
- 基金配置归一化、持仓写入、配置持久化优先复用 `funds_manager.py`。
- 保持对简写基金项和字典基金项的兼容，字典项中的 `name`、`holding` 仍为可选。
- 持仓校验保持严格：必须是数值，`units > 0`，`cost_amount >= 0`。

## 默认安全工作流
- 先阅读目标函数及其邻近辅助函数，再动手修改。
- 修改行为时同步更新测试，或补一条聚焦的回归测试。
- 先运行最小相关命令验证，再根据改动范围决定是否跑完整测试。
- 汇总结果时明确说明是否涉及用户可见文本、配置结构、网络回退行为或打包流程变化。

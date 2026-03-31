# 市场监视小工具 基你太美

Flet 桌面程序，通过下拉菜单查看上证指数、伦敦黄金现货，以及自定义基金的实时估值，支持自动刷新、分市场倒计时、K 线详情（日K / 近半年 / 月K）。

## 运行
1. 安装依赖：
   ```bash
   python -m pip install -r requirements.txt
   ```
2. 启动应用：
   ```bash
   python main.py
   ```

## 配置基金下拉菜单
- 开发运行（`python main.py`）：读取项目根目录的 `funds.json`（也兼容 `fund.json`）。
- 打包为 exe 后：读取 `main.exe` 同级目录的 `funds.json`（也兼容 `fund.json`）。

在配置文件中只需要填写基金代码即可（名称可省略，程序会按代码自动查询并展示）,注意最后一行后没有逗号。示例：
   ```json
   {
      "funds": [
         { "code": "110022" },
         { "code": "161725" }
      ]
   }
   ```
- 也支持更简写的配置：
   ```json
   {
      "funds": ["110022", "161725"]
   }
   ```
- 运行时会自动读取该文件并在下拉菜单中加入对应基金，展示估算净值、近3/7/15/30 日累计涨跌，以及 MA5/MA10/MA20/MA250，并显示当前估值相对均线的偏离。
- 如需预置持仓，也可在基金项中添加 `holding`：
   ```json
   {
      "funds": [
         {
            "code": "110022",
            "holding": {
               "units": 1234.56,
               "cost_amount": 1500.00
            }
         }
      ]
   }
   ```
  其中 `units` 表示持有份额，`cost_amount` 表示当前总持仓成本。

说明：
- “基金列表”页展示基金名称、当日估值涨跌幅、上一交易日涨跌幅、持仓份额、持仓成本、当日盈亏、累计盈亏；“实时估值”和“净值变化”列支持上/下三角按钮升序、降序排序。
- “基金列表”页右上角支持“+”添加：输入基金代码回车后可预览基金，点击“添加到列表”会写入 `funds.json` 并立即刷新列表。
- “基金列表”页每只基金支持“录入持仓 / 编辑持仓”，保存后会按当前估值与上一交易日净值计算当日盈亏，并按当前市值与持仓成本计算累计盈亏。

## 打包为单文件 exe
1. 安装打包工具（一次即可）：
   ```bash
   python -m pip install pyinstaller
   ```
2. 打包：
   ```bash
   pyinstaller main.spec
   ```
3. 生成的可执行文件位于 `dist/main.exe`。
4. 将 `funds.json`（或 `fund.json`）放到 `dist/main.exe` 同级目录，双击运行即可修改基金列表（无需重新打包）。

### 一键打包（bat）
- 运行项目根目录的 `build_exe.bat`。
- 按提示输入 exe 名称（不含 `.exe`）。
- 打包完成后会在 `dist` 目录生成对应名称的文件，例如输入 `基你太美0303`，输出 `dist\基你太美0303.exe`。

## 说明
- 市场页指数：仅使用 AkShare 的 Eastmoney 指数接口，按 `MARKET_INDEX_CONFIGS` 中的 `code`、`name`、`category` 配置并匹配数据。
- 实时报价：黄金使用 AkShare，基金使用天天基金 `.js` 接口 + akshare 补充历史数据。
- K 线数据：优先 Stooq（上证 `000001.ss`，黄金 `xauusd`），失败时回落到 Yahoo Finance（`000001.SS` / `XAUUSD=X`），支持日K/近半年/月K。
- 黄金折算人民币：用 Yahoo 汇率 `USDCNY=X` 估算，按 1 盎司=31.1035 克换算。
- 市场数据默认 5 分钟自动刷新，可在 `REFRESH_MS` 中调整（毫秒）。
- 倒计时每秒更新；如需关闭，删除 `self.after(COUNTDOWN_MS, self.update_countdown)`。
- 若 K 线拉取失败，通常是网络或 Yahoo 访问受限，可稍后重试。

## EXE 常见排障
- 指数提示“EM无可用数据”时，请先看日志：`%LOCALAPPDATA%/market_watch/app.log`。
- 若源码可用但 EXE 失败，通常是运行环境网络策略差异（代理、白名单、证书链）或本机依赖缓存异常。
- 建议优先使用 `main.spec` 打包，避免遗漏运行时依赖与证书资源。

## 代理开发约束
- 本仓库中的智能编码代理与用户交流时统一使用中文。
- 本仓库中的智能编码代理编写或修改 Markdown 文档时统一使用中文。
- 代理执行代码修改时应优先遵循仓库根目录下的 `AGENTS.md`。
- 代理还应同时遵循 `.github/copilot-instructions.md` 中的仓库规则。
- 市场指数页面仅允许使用 AkShare 的 Eastmoney 指数数据，不要为该页面重新引入 Sina 或其他数据源回退逻辑。
- 市场指数集合与匹配规则必须继续由 `MARKET_INDEX_CONFIGS` 驱动，并保持“代码优先”。
- 基金配置归一化、持仓校验、配置持久化优先复用 `funds_manager.py` 中已有辅助函数。
- 正常功能开发中不要修改 `build/`、`dist/` 下的生成文件，除非任务明确与打包产物有关。
- 新增或修改逻辑后，优先补充或更新 `tests/` 下的针对性测试。
- 单个测试优先使用 `pytest` 运行，例如：`python -m pytest tests/test_funds_manager.py::FundsManagerTests::test_add_fund_and_save_preserves_existing_holding -q`

# trade_digest — A股交易简报自动推送

自动采集 A 股和港股市场数据，通过 LLM 生成交易简报，支持邮件、飞书、Telegram 等多渠道推送。

## 功能

- **大盘概览**：A 股三大指数、上涨下跌家数、北向资金、融资融券、港股行情、美股期货
- **板块资金流**：行业板块主力资金净流入/流出 TopN 排名
- **关注 ETF 行情**：自定义 ETF 观察列表的涨跌幅和成交额
- **宏观数据**：中国/美国重要经济数据日历及超预期提醒（CPI、PMI、GDP 等）
- **持仓提醒**：基于持仓成本价的触发式告警（价格突破、回撤等）
- **AI 解读**：LLM 对市场概况、板块轮动、宏观数据的综合分析 + 定投建议
- **多渠道推送**：邮件（默认）、飞书 Webhook、Telegram Bot
- **Health 监控**：自动追踪 LLM 调用和邮件发送成功率，异常时在简报中提示

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/syuchua/tradeBrief
cd trade_digest
```

### 2. 安装依赖

```bash
uv sync
```

### 3. 配置文件

复制示例配置并填写：

```bash
cp trade_digest/config/settings.example.yaml trade_digest/config/settings.yaml
cp trade_digest/config/holdings.example.yaml trade_digest/config/holdings.yaml
```

编辑 `trade_digest/config/settings.yaml` 中的 `email.recipients` 等字段。

### 4. 环境变量

在 `trade_digest/config/.env` 中配置以下变量（本地开发），或直接在系统环境变量中设置。

> **注意：至少需要配置一个通知渠道**（邮件 / 飞书 / Telegram），否则运行时会报错 `没有配置任何通知渠道`。你可以同时配置多个渠道，程序会并行推送到所有已配置的渠道。

```bash
# LLM 配置（必需）
LLM_PROVIDER=openai       # openai 或 anthropic
LLM_API_KEY=sk-xxx        # API 密钥
LLM_BASE_URL=https://api.openai.com/v1  # 可选：兼容 OpenAI API 的代理地址
LLM_MODEL=gpt-4o-mini     # 可选：模型名称

# === 通知渠道（至少选一个） ===

# 方式一：邮件
SMTP_PROVIDER=qq          # 预设模式：qq/gmail/163/outlook，自动查找 host/port
SMTP_USER=your@qq.com     # SMTP 登录用户
SMTP_PASSWORD=your_code   # SMTP 授权码（非邮箱密码）

# 方式二：飞书机器人（可选）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 方式三：Telegram Bot（可选）
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
```

#### 预设模式 vs 显式模式

使用 `SMTP_PROVIDER` 时，程序自动从预设表查找 host 和 port：

| Provider | Host | Port |
|----------|------|------|
| `qq` | smtp.qq.com | 465 |
| `163` | smtp.163.com | 465 |
| `gmail` | smtp.gmail.com | 587 |
| `outlook` | smtp-mail.outlook.com | 587 |

也可以使用显式模式（不设 `SMTP_PROVIDER`，直接填 `SMTP_HOST` / `SMTP_PORT`）。

### 5. 命令行运行

```bash
# 早盘简报
uv run python -m trade_digest.main --session morning

# 晚间简报
uv run python -m trade_digest.main --session evening

# 强制运行（周末/节假日测试时跳过交易日检查）
uv run python -m trade_digest.main --session morning --force
```

`--force` 参数在非交易日也能运行，方便调试和验证配置。

## 程序化调用

除了命令行，也可以在脚本、Web 服务或 Jupyter Notebook 中调用 API：

```python
from trade_digest.api import generate_report, export_html, export_markdown

# 生成早盘简报（含 LLM 解读）
report = generate_report("morning")
print(report.llm_result["market_summary"])

# 只采集数据 + 渲染，不调用 LLM
report = generate_report("evening", enable_llm=False)

# 周末强制运行（跳过交易日检查）
report = generate_report("morning", force=True)

# 导出为 HTML 文件
path = export_html("evening", output_dir="./reports")

# 导出为 Markdown 文件
path = export_markdown("morning", output_dir="./reports")
```

## 目录结构

```
trade_digest/
├── main.py                  # CLI 入口 + 数据采集调度 (_collect_data)
├── api.py                   # 程序化 API (generate_report / export_html / export_markdown)
├── health.py                # 健康监控与运行记录
├── logging_config.py        # 日志配置（文件轮转 + 控制台输出）
├── state.py                 # 持久化状态（定投运行日期 / LLM 缓存）
├── config/
│   ├── loader.py            # YAML 配置加载
│   ├── settings.example.yaml
│   ├── holdings.example.yaml
│   └── .env                 # 环境变量（不入 git）
├── data/
│   ├── calendar.py          # A 股交易日历
│   ├── market_overview.py   # 大盘概览数据
│   ├── sector_flow.py       # 板块资金流 + ETF 行情
│   ├── holdings_quotes.py   # 持仓行情查询
│   ├── macro.py             # 宏观经济数据
│   └── news.py              # 财经新闻
├── analysis/
│   ├── holdings_alert.py    # 持仓告警逻辑
│   ├── llm_client.py        # LLM 客户端（OpenAI / Anthropic）
│   └── synthesize.py        # Prompt 构建 + 结果解析
└── notify/
    ├── emailer.py           # HTML 邮件渲染 + SMTP 发送
    ├── feishu.py            # 飞书自定义机器人推送
    ├── telegram.py          # Telegram Bot 推送
    └── dispatch.py          # 多渠道调度器
```

## GitHub Actions 自动推送

项目包含 GitHub Actions 工作流（`.github/workflows/trade-digest.yml`），在每个交易日自动运行早晚盘推送。

### 配置文件的两种模式

workflow 会在运行前检查 `SETTINGS_YAML` / `HOLDINGS_YAML` 这两个 Secret：**如果配置了，用 Secret 内容覆盖仓库里的 yaml 文件；如果没配置，直接使用仓库里已有的 `trade_digest/config/settings.yaml` / `holdings.yaml`。**

| 模式 | 适用场景 | 前提 |
|------|----------|------|
| **Secrets 模式**（推荐） | 仓库是 public，或不想把持仓信息提交到 git 历史 | 配置 `SETTINGS_YAML` / `HOLDINGS_YAML` 两个 Secret |
| **仓库文件模式** | 仓库是 **private**，可以接受真实持仓写进 git 历史 | 不配置这两个 Secret，直接把真实 `settings.yaml` / `holdings.yaml` 提交到仓库 |

> ⚠️ **仓库文件模式只能用于 private 仓库。** 如果仓库是 public 的，任何人都能看到你的持仓、成本价、告警阈值等信息。`.gitignore` 只能防止本地 `git add` 误提交，无法阻止你手动在 GitHub 网页上创建/编辑这两个文件——一旦这样做，它们就已经进入 git 历史，即使之后删除，历史记录里仍能找到。

### 必需的 Secrets

| Secret | 说明 |
|--------|------|
| `LLM_PROVIDER` | `openai` 或 `anthropic` |
| `LLM_API_KEY` | LLM API 密钥 |
| `LLM_BASE_URL` | 可选：API 代理地址（如 DeepSeek） |
| `LLM_MODEL` | 可选：模型名称（默认 `gpt-4o-mini`） |

### 可选：Secrets 模式所需

| Secret | 说明 |
|--------|------|
| `SETTINGS_YAML` | `settings.yaml` 文件完整内容 |
| `HOLDINGS_YAML` | `holdings.yaml` 文件完整内容 |

### 通知渠道 Secrets（至少选一个）

| Secret | 对应渠道 | 说明 |
|--------|----------|------|
| `SMTP_PROVIDER` | 邮件 | 预设名称：`qq` / `gmail` / `163` / `outlook` |
| `SMTP_USER` | 邮件 | SMTP 登录用户 |
| `SMTP_PASSWORD` | 邮件 | SMTP 授权码 |
| `FEISHU_WEBHOOK_URL` | 飞书 | 可选：飞书机器人 Webhook 地址 |
| `TELEGRAM_BOT_TOKEN` | Telegram | 可选：Bot Token |
| `TELEGRAM_CHAT_ID` | Telegram | 可选：目标 Chat ID |

> 如果邮件、飞书、Telegram 都不想用，也可以只配显式 SMTP（`SMTP_HOST` + `SMTP_PORT`）。**只要有一个渠道配好即可。**

### 定时 + 手动触发

定时间表：周一至周五 **早盘 09:30**（UTC 01:30）、**晚盘 15:30**（UTC 07:30）。

手动触发：Actions 页面 → 选择 workflow → Run workflow → 选择 `morning` 或 `evening`。

### 配置步骤

1. 仓库页面 → Settings → Secrets and variables → Actions → New repository secret
2. 逐个添加上述 Secrets
3. 去 Actions 页面手动触发一次 `morning` 验证

## 许可证

[MIT](./LICENSE)

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
git clone <your-repo-url>
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

在 `trade_digest/config/.env` 中配置以下变量（本地开发），或直接在系统环境变量中设置：

```bash
# 邮件配置（必需）
SMTP_PROVIDER=qq          # 预设模式：qq/gmail/163/outlook，自动查找 host/port
SMTP_USER=your@qq.com     # SMTP 登录用户
SMTP_PASSWORD=your_code   # SMTP 授权码（非邮箱密码）

# LLM 配置（必需）
LLM_PROVIDER=openai       # openai 或 anthropic
LLM_API_KEY=sk-xxx        # API 密钥
LLM_BASE_URL=https://api.openai.com/v1  # 可选：兼容 OpenAI API 的代理地址
LLM_MODEL=gpt-4o-mini     # 可选：模型名称

# 可选通知渠道
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
```

### 5. 命令行运行

```bash
# 早盘简报
uv run python -m trade_digest.main --session morning

# 晚间简报
uv run python -m trade_digest.main --session evening
```

## 程序化调用

除了命令行，也可以在脚本、Web 服务或 Jupyter Notebook 中调用 API：

```python
from trade_digest.api import generate_report, export_html, export_markdown

# 生成早盘简报（含 LLM 解读）
report = generate_report("morning")
print(report.llm_result["market_summary"])

# 只采集数据 + 渲染，不调用 LLM
report = generate_report("evening", enable_llm=False)

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
    └── emailer.py           # HTML 邮件渲染 + SMTP 发送
```

## GitHub Actions 自动推送

项目包含 GitHub Actions 工作流（`.github/workflows/trade-digest.yml`），配置好以下 Secrets 即可实现每个交易日自动推送：

| Secret | 说明 |
|--------|------|
| `SETTINGS_YAML` | `settings.yaml` 文件内容 |
| `HOLDINGS_YAML` | `holdings.yaml` 文件内容 |
| `SMTP_PROVIDER` | SMTP 预设名称（如 `qq`） |
| `SMTP_USER` | SMTP 登录用户 |
| `SMTP_PASSWORD` | SMTP 授权码 |
| `LLM_PROVIDER` | `openai` 或 `anthropic` |
| `LLM_API_KEY` | LLM API 密钥 |
| `LLM_BASE_URL` | 可选：API 代理地址 |
| `LLM_MODEL` | 可选：模型名称 |

定时间表：周一至周五早盘 UTC 01:30（北京时间 09:30），晚盘 UTC 07:30（北京时间 15:30）。

## 许可证

MIT

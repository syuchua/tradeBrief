# 金融趋势聚合分析工具 — Phase 1 (MVP) 设计

日期：2026-07-02

## 1. 目标与范围

面向个人使用的A股交易日双时段简报工具：每个A股交易日发送两封邮件，汇总大盘/资金流/多空比例/中美宏观/消息面动态，并结合用户具体持仓给出个性化提醒和参考建议。非交易日自动跳过。

本阶段（Phase 1）范围：
- 数据 → 规则判断 → LLM综合解读 → 邮件发送的完整链路
- 本地运行验证，暂不锁定最终部署平台（GitHub Actions / Cloudflare / 自建服务器留待后续阶段决定）

不在本阶段范围：
- 短信通知
- 可视化图表
- 精确的分钟级/实时监控（本工具定位为低频、每日两次的辅助参考，不做高灵敏度盯盘）
- 多智能体（multi-agent）架构（用分域结构化单次LLM调用替代，理由见第7节）

## 2. 推送时段

| 场次 | 时间 | 侧重 |
|---|---|---|
| 早盘 | 10:30 | A股开盘1小时资金流/涨跌家数 + 隔夜美股收盘总结 + 当前日韩股市（已开盘） |
| 晚间 | 20:00-20:30 | A股完整收盘总结 + 美股盘前期货/消息（美股21:30/22:30开盘前的预览） |

两场次均先经过交易日历判断，非A股交易日两场都跳过。

## 3. 系统架构

```
trade_digest/
├── config/
│   ├── holdings.yaml        # 持仓配置（手动维护）
│   └── settings.yaml        # 关注ETF清单、板块Top N、优先级阈值、LLM/邮件非敏感配置
├── state/
│   ├── macro_last_seen.json     # 宏观指标"上次见过的最新日期"缓存
│   └── dca_strategy_last_run.json  # 定投策略上次生成日期缓存
├── data/
│   ├── calendar.py          # A股交易日历判断
│   ├── market_overview.py   # 大盘指数、涨跌家数、多空比例(两融)、北向资金、隔夜美股/日韩/美股盘前
│   ├── sector_flow.py       # 全市场行业/概念资金流排行 + 关注ETF清单行情
│   ├── macro.py             # 中美宏观数据，含"是否新发布"判断（对比state缓存）
│   ├── news.py              # 财经快讯抓取（用于消息面优先级分级）
│   └── holdings_quotes.py   # 持仓标的（黄金/证券/ETF）现价
├── analysis/
│   ├── holdings_alert.py    # 目标价/止盈止损规则触发判断（结构化condition，非任意表达式）
│   ├── llm_client.py        # LLM抽象层：OpenAI兼容 / Anthropic 双实现，环境变量切换
│   └── synthesize.py        # 分域组织数据 → 单次LLM调用 → 生成解读/打分/分级/策略建议
├── notify/
│   └── emailer.py           # 渲染精简HTML + SMTP发送
└── main.py                  # 入口：--session morning|evening
```

## 4. 数据流

1. `main.py` 接收 `--session morning|evening` 参数
2. `calendar.py` 判断今日是否A股交易日，非交易日直接退出（不抓数据、不调用LLM、不发邮件）
3. 并行抓取：大盘概览、板块/ETF资金流、持仓现价、财经快讯；`macro.py`额外对比 `state/macro_last_seen.json` 判断当天是否有新宏观数据发布
4. `holdings_alert.py` 用holdings.yaml中的规则做纯代码判断（如黄金现价≥4380）
5. 判断是否到期需要生成"定投策略参考"（对比 `state/dca_strategy_last_run.json`，仅晚间场次可能触发）
6. `synthesize.py` 把以上数据分域打包为结构化payload，单次调用LLM，返回结构化JSON（市场解读、板块解读、宏观解读、持仓打分、优先级分级消息、定投策略建议）
7. `emailer.py` 按session类型渲染对应邮件板块并通过SMTP发送
8. 任一环节的数据缺失/失败仅做局部降级，不阻断整体流程（见第10节）

## 5. 数据源（akshare为主，具体函数名以实现时核实文档为准）

| 模块 | 数据 | 参考接口 |
|---|---|---|
| 交易日历 | A股是否交易日判断 | `tool_trade_date_hist_sina` |
| 大盘概览 | 指数行情、涨跌家数、赚钱效应 | `stock_zh_index_spot_em`、`stock_market_activity_legu` |
| 多空比例 | 两融数据 | `stock_margin_detail_sse` / `szse` |
| 北向资金 | 沪深港通资金流向 | `stock_hsgt_fund_flow_summary_em` |
| 隔夜美股/日韩/美股盘前 | 美股三大指数、期货、日经/KOSPI | `index_us_stock_sina`、`index_global_hist_em` |
| 全市场资金流排行 | 行业+概念板块净流入/流出Top N | `stock_sector_fund_flow_rank`、`stock_fund_flow_concept` |
| 关注ETF行情 | 持仓相关ETF涨跌幅/成交额 | `fund_etf_spot_em` |
| 中国宏观 | LPR/CPI/PMI/社融/GDP，含今值/预测值/前值 | `macro_china_lpr`、`macro_china_cpi_yearly`、`macro_china_gdp_yearly`等 |
| 美国及各国宏观 | 联储利率、CPI、非农，含今值/预测值/前值 | `macro_bank_usa_interest_rate`、`macro_usa_cpi_monthly`等 |
| 财经快讯 | 消息面原始素材 | 东方财富全球财经快讯 / 财联社电报类接口 |
| 持仓现价 | 黄金/证券股/场内基金 | `fund_etf_spot_em`、`stock_zh_a_spot_em` |

宏观数据的"今值 vs 预测值"用于数值化判断是否超预期（见第8节），若个别接口缺少预测值字段，退化为LLM读新闻文本判断。

## 6. 持仓配置 `holdings.yaml`

```yaml
as_of: 2026-07-02
categories:
  fund:                     # 四成，长期定投
    total_weight: 0.40
    positions:
      - {name: 科技板块基金, code: "XXXXXX", weight_within_category: 0.5}
      - {name: 纳指,   code: "513100", weight_within_category: 0.15}
      - {name: 标普,   code: "513500", weight_within_category: 0.10}
      - {name: 恒生科技(定投), code: "513180", weight_within_category: 0.10}
      - {name: 红利,   code: "510880", weight_within_category: 0.10}
      - {name: 宽基,   code: "510300", weight_within_category: 0.05}

  gold:                     # 两成，被套，有明确减仓触发线
    total_weight: 0.20
    positions:
      - name: 黄金
        code: "518880"
        cost_price: 4350
        alerts:
          - {condition: "price >= 4380", action: "反弹至4380，考虑减仓至10%以下"}

  securities_trading:       # 一成多，场内短线
    total_weight: 0.13
    positions:
      - {name: 券商, code: "512880", weight_within_category: 0.5}
      - {name: 恒生科技(短线), code: "513180", weight_within_category: 0.08, note: "已割肉一次"}
      - {name: 现金/子弹, weight_within_category: 0.42}
```

`alerts.condition` 为结构化的"字段+运算符+阈值"，由代码解析比较，不做任意表达式求值。

## 7. 个股打分与定投策略分层

两种不同性质、不同频率的参考建议，不合并处理：

**每日打分（仅短线仓位 + 黄金）**：`fund`类目下的定投标的**不做**每日看多看空打分——定投逻辑是分批建仓而非择时，天天打分容易诱导偏离定投纪律。打分只针对 `securities_trading`（券商/恒科短线仓）和 `gold`，随每日两次报告输出。

**定投中长期策略参考（仅`fund`类目，周频）**：默认每7天（`settings.yaml`可配置）重新生成一次，其余时间从`state/dca_strategy_last_run.json`对应的缓存内容展示"更新于XX日期"，避免逐日数据抖动导致前后矛盾的建议，也节省LLM调用。输入维度：近4周价格趋势、板块资金流中期方向、宏观环境定性（加息/降息周期、流动性松紧）。输出：每个定投标的"继续定投/可考虑加大/可考虑阶段性减少"三档定性建议+理由，并注明"仅供参考，不构成精确择时信号"。仅在晚间场次展示。

**为何不用真正的多智能体(multi-agent)架构**：多agent（每个数据域独立LLM调用+编排层汇总）能避免单一大prompt里信号被强势数据（如突发新闻）稀释，但会成倍增加调用次数、延迟和编排复杂度。本工具是低频（每日两次）个人工具，用"单次调用+分域结构化payload+要求模型分域给结论再综合"的方式，以更低成本拿到多agent的大部分收益（分域清晰、分歧可见），复杂度留给未来若发现质量不够时再升级。

## 8. 消息优先级分级

四档分类标准（写入LLM system prompt）：

| 档位 | 定义 | 判定方式 |
|---|---|---|
| 第一档 | 黑天鹅、重大科技突破、泡沫破裂 | LLM读新闻文本判断（预期数量极少，多数报告应为空，属正常） |
| 第二档 | 市场可快速消化的重大利空/利好；大幅超预期的宏观数据 | 宏观数据用"今值 vs 预测值"数值化规则判断；非宏观事件由LLM读新闻判断 |
| 第三档 | 高权重/高热度企业财报、订单；与预期差距不大的常规宏观数据 | LLM判断，邮件中限制展示条数 |
| 第四档 | 对市场冲击不大的消息，或用户不关注板块的消息 | LLM判断，邮件中默认不展开，仅一句话汇总条数 |

命中第一档不触发额外的即时/带外推送，仍在下一次定时邮件中醒目展示——与"不需要高灵敏度、两次邮件即可"的初衷保持一致。

## 9. LLM 集成设计

**Provider抽象**（`analysis/llm_client.py`）：定义统一接口，提供 `OpenAICompatibleClient`（覆盖OpenAI官方及DeepSeek/通义千问/Kimi等所有OpenAI兼容接口）和 `AnthropicClient`（Claude API）两个实现，通过环境变量 `LLM_PROVIDER`/`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` 切换，上层`synthesize.py`代码不感知具体provider。两个实现均要求返回结构化JSON（OpenAI用`response_format=json_object`，Anthropic用tool-use强制schema），避免为不同provider写不同的自然语言解析逻辑。

**单次调用，分域payload**：

```json
{
  "market_overview": {...},
  "sector_flow": {...},
  "macro_updates": [],
  "news_items": [...],
  "watchlist_tactical": [
    {"name": "黄金", "code": "518880", "price": 4360, "cost_price": 4350, "alert_triggered": false}
  ],
  "dca_strategy_due": false
}
```

**输出schema**：`market_summary`、`sector_highlights`、`macro_commentary`(可null)、`tactical_scores`(逐标的打分+理由)、`priority_alerts`(见第8节的四档分类数组)、`dca_strategy`(仅到期时输出)。`emailer.py`直接按字段渲染，不解析自然语言。

System prompt角色设定为"严谨克制的证券分析助手，只做参考性判断，不给绝对化买卖建议，明确标注不确定性"。

## 10. 邮件渲染

精简HTML，按顺序：标题(日期+场次) → 优先级预警区(仅命中第一/二档时出现) → 大盘概览(含场次专属的隔夜美股/日韩或美股盘前) → 板块资金流 → 宏观数据(仅当天有新发布时出现) → 持仓提醒(黄金目标价+短线仓位打分) → 定投策略参考(仅晚间场且到期/有缓存时出现) → 第三档消息(限条数)+第四档汇总一句话 → 底部数据来源/生成时间/免责声明。不做图表可视化。

## 11. 调度设计

`main.py --session morning|evening`：脚本本身不感知当前时间，只按传入的session类型工作，具体"何时调用"完全交给外部调度器决定，便于后续从本地任务计划切换到GitHub Actions/云服务器而不改动业务代码。交易日历判断在入口最前执行。

## 12. 错误处理与降级

- 单个数据源抓取失败 → 该板块标注"数据缺失"，不阻断其他板块和邮件发送
- LLM调用失败 → 跳过所有解读/打分/分级内容，仅发送原始数据，邮件顶部提示"AI解读生成失败"
- 状态缓存文件（宏观/定投策略）读取失败 → 视为"无新内容"，不阻断流程
- 状态缓存文件首次不存在（首次运行）→ 静默写入当前最新日期作为基线，本次不判定为"新发布"，避免第一次运行时把所有历史宏观数据当成"今日新发布"刷屏
- 所有异常记录本地日志，便于事后排查

## 13. 测试计划

- 各`data/*.py`模块用mock数据测试解析逻辑，不依赖真实网络请求
- `holdings_alert.py`规则判断边界值测试
- `llm_client.py`用录制的fixture响应验证两个provider输出格式一致性
- 集成测试：mock全套数据跑通`main.py`，验证邮件HTML包含预期板块，mock SMTP不真实发送
- 手动验证：配置真实SMTP和至少一个LLM provider，跑一次真实morning/evening session核对邮件效果

## 14. 后续阶段（超出本次范围，仅记录方向）

- Phase 2：确定并迁移部署平台（GitHub Actions / Cloudflare / 自建服务器），补充幂等重跑保护
- Phase 3：视效果决定是否升级为真正的多agent架构、接入更多板块/资产类别
- Phase 4：短信通道、可视化图表等增强

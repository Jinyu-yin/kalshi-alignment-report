# Prediction Market Macro Signal Pipeline

一个面向分析师的研究框架：将 Polymarket/Kalshi 市场数据转化为可解释的宏观事件信号，并评估其对利率品种（默认 `ZT`）未来收益的预测能力。

---

## 一、对参考报告 `just_reference.pdf` 的研究思路拆解

你给的参考报告虽然是债券研究语境，但方法论非常清晰，可以抽象成 4 层：

1. **事件标准化与时点一致性（PIT）**
   - 核心不是“事后看对不对”，而是“在当时可得信息下，信号是否有效”。
2. **先做单因子检验，再做组合策略**
   - 先确认每个因子的方向、显著性和稳定性，再进入策略合成。
3. **把研究结果可视化成分析师图表包**
   - 时间序列图、分布图、分组对比图、案例窗口图，支持“讲故事”。
4. **最后落地到交易可解释指标**
   - 胜率、收益分布、Profit Factor、不同窗口对比，而不只看单一收益率。

本项目已按这个逻辑升级：在 Step04 前新增单因子检测，并新增报告图表输出步骤。

---

## 二、研究目标（Analyst View）

本项目核心不是“预测单个 market 是否命中”，而是回答三个更有交易价值的问题：

1. **市场在某一时刻是否出现了宏观信息冲击？**
2. **冲击是“方向性跳跃”还是“阈值反转”？**
3. **这些冲击能否转化为对利率资产未来收益的统计优势？**

因此，pipeline 被设计为“数据标准化 -> 主题归因 -> 单因子验证 -> 策略信号 -> 回测 -> 图表报告”的闭环。

---

## 三、总体框架（8-Step Pipeline）

所有脚本位于 `pipeline/`，建议按 `00 -> 06` 顺序执行。

### Step 00: 主题市场构建
- 脚本：`pipeline/00_build_topic_jsons.py`
- 作用：将 Polymarket 市场按宏观主题归类（如 `central_banks`, `inflation`）
- 数据来源：
  - 优先：`data/polymarket/markets/*.parquet`
  - 兜底：Gamma API 自动拉取并缓存
- 产出：
  - `output/markets/categories/poly_{topic}_markets.jsonl`
  - `output/markets/categories/poly_{topic}_ids.csv`
  - `output/markets/poly_topics_summary.csv`

### Step 01: 按主题落地市场清单
- 脚本：`pipeline/01_load_markets.py`
- 作用：把 Step00 的主题结果转换为标准市场表
- 产出：
  - `output/pipeline/topics/{topic}/markets.csv`
  - `output/pipeline/markets.csv`

### Step 02: 事件方向与强度解析
- 脚本：`pipeline/02_ai_event_parse.py`
- 作用：对市场问题文本打标签（`direction`, `magnitude`, `weight`）
- 机制：
  - 有 `N1N_API_KEY`：使用 LLM
  - 无 key：自动使用本地 heuristic fallback（保证可跑）
- 产出：
  - `output/pipeline/topics/{topic}/events.csv`
  - `output/pipeline/events.csv`

### Step 03: 交易/概率时间序列构建
- 脚本：`pipeline/03_build_market_prob.py`
- 作用：生成市场级概率序列（分钟级）
- 数据来源：
  - 优先：`data/polymarket/trades/*.parquet` 聚合得到 `prob/volume/trades`
  - 兜底：若无 trades，用市场快照概率生成可运行版本
- 产出：
  - `output/pipeline/topics/{topic}/market_prob/polymarket_{market_id}.parquet`

### Step 03b: 单因子检测（新增）
- 脚本：`pipeline/03b_single_factor_test.py`
- 作用：在策略生成前先验证因子有效性（IC、多空价差、命中率）
- 因子示例：
  - `dprob`
  - `dlogit`
  - `factor_jump`
  - `factor_reversal`
  - `factor_vol_jump`
- 产出：
  - `output/pipeline/topics/{topic}/single_factor/factor_scores.csv`
  - `output/pipeline/topics/{topic}/single_factor/thresholds.csv`
  - `output/pipeline/topics/{topic}/single_factor/factor_observations.parquet`
  - `output/pipeline/single_factor_summary.csv`

### Step 04: 双策略信号生成（重点）
- 脚本：`pipeline/04_build_event_signal.py`
- 作用：基于 market_prob + event meta，输出两类策略信号
- 关键升级：
  - 从 Step03b 自动读取 topic 阈值（`thresholds.csv`），不再全局固定阈值
- 产出目录（每个 topic）：
  - `output/pipeline/topics/{topic}/signals/jump/`
  - `output/pipeline/topics/{topic}/signals/reversal/`
- 每个目录包含：
  - `signal_market.parquet`（市场级）
  - `event_signal.parquet`（主题聚合级）

### Step 05: 按策略分别回测
- 脚本：`pipeline/05_predict_returns.py`
- 作用：分别评估 `jump` 与 `reversal` 对未来收益的解释力
- 默认标的：`ZT_1min.csv`（自动从 `data/macro` 或 `src/analysis` 查找）
- 产出：
  - `output/event_backtest_results.csv`

### Step 06: 报告图表包生成（新增）
- 脚本：`pipeline/06_build_report_charts.py`
- 作用：自动输出“分析师风格”图表和案例文件
- 产出目录：`output/report/`
- 主要输出：
  - `single_factor_ic_heatmap.png`
  - `single_factor_spread_ranking.png`
  - `backtest_winrate_by_horizon.png`
  - `backtest_profit_factor_topic_24h.png`
  - `{topic}_signal_timeseries.png`
  - `{topic}_signal_distribution.png`
  - `{topic}_case_top_signals.csv`
  - `REPORT.md`（图表索引报告）

---

## 四、Step04 双策略方法说明（核心）

### 1) Jump Strategy（量价跳跃）

逻辑：当市场概率在短时间内发生显著跳变，且伴随成交量权重时，视为信息冲击。

- 基础变量：`dprob`, `dlogit`, `volume`
- 过滤条件：`abs(dprob) > topic_specific_threshold`
- 市场级打分（示意）：
  - `score = direction * magnitude * sign(dlogit) * sqrt(abs(dlogit))`
- 主题级聚合输出：
  - `signal_sum`
  - `signal_mean`
  - `signal_volume_weighted`

### 2) Reversal Strategy（阈值反转）

逻辑：反转阈值不固定为 50%，对“同题多选项 market”使用动态阈值。

- 同题组选项识别：
  - 由 `markets.csv` 的问题文本生成 `group_key`
- 动态 pivot：
  - 单市场：`pivot = 0.5`
  - 多选项组：`pivot = 1 / group_size`
- 触发条件：
  - 概率从 pivot 一侧穿越到另一侧
  - 且穿越幅度超过 topic-specific 最小阈值（来自 Step03b）
- 输出结构与 Jump 一致，便于横向比较

---

## 五、输入输出与路径约定

### 关键输入
- `data/polymarket/markets/*.parquet`（推荐）
- `data/polymarket/trades/*.parquet`（推荐）
- `data/macro/ZT_1min.csv` 或 `src/analysis/ZT_1min.csv`（回测价格）

### 关键输出
- `output/markets/`：主题市场分类结果
- `output/pipeline/topics/{topic}/`：每个主题完整中间产物
- `output/event_backtest_results.csv`：最终策略评估表
- `output/report/`：报告图表包

---

## 六、快速运行（Windows / PowerShell）

### 逐步执行

```powershell
.\.venv\Scripts\python.exe "pipeline/00_build_topic_jsons.py"
.\.venv\Scripts\python.exe "pipeline/01_load_markets.py"
.\.venv\Scripts\python.exe "pipeline/02_ai_event_parse.py"
.\.venv\Scripts\python.exe "pipeline/03_build_market_prob.py"
.\.venv\Scripts\python.exe "pipeline/03b_single_factor_test.py"
.\.venv\Scripts\python.exe "pipeline/04_build_event_signal.py"
.\.venv\Scripts\python.exe "pipeline/05_predict_returns.py"
.\.venv\Scripts\python.exe "pipeline/06_build_report_charts.py"
```

### 一键执行

```powershell
.\.venv\Scripts\python.exe "run_pipeline.py"
```

如需启用 Step02 的 LLM 解析：

```powershell
$env:N1N_API_KEY="your_api_key"
```

---

## 七、结果解读建议（Analyst Notes）

1. **先看单因子**：`single_factor_summary.csv`
   - 哪些因子在多数 topic 上 IC 为正、spread 稳定。
2. **再看策略层**：`event_backtest_results.csv`
   - `jump` vs `reversal` 在不同 horizon 的胜率和 PF。
3. **最后看案例层**：`output/report/*case_top_signals.csv`
   - 验证高信号窗口是否与宏观事件叙事一致。

建议不要只看单个指标；至少联合观察 `n_trades`, `win_rate`, `profit_factor`, `avg_strat_ret`。

---

## 八、模型与工程边界

- 本框架偏“研究与策略筛选”，不是生产交易系统。
- Step02 的语义归因对提示词/模型敏感，建议固定版本并做回溯记录。
- Reversal 的组选项识别当前是文本规则法，可继续升级为显式事件图谱匹配。
- 报告图表层当前聚焦“研究展示”，尚未纳入交易成本与滑点净值曲线。

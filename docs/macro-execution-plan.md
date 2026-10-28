# Kalshi Macro Composite Strategy Execution Plan

## 总目标

构建一个比单一 FFR 更完整的 Kalshi 宏观预测因子系统，用于交易真实可交易长久期美债 ETF，例如：

- `TLT`
- `EDV`
- `ZROZ`
- `GOVZ`

核心思想：

```text
看多长债 =
    Fed 更鸽
  + 通胀预期下降
  + 就业恶化
  + 未来降息路径增加
```

最终输出：

1. 完整宏观预测面板；
2. 单因子回测；
3. 多因子合成回测；
4. 稳健性检验；
5. 报告与图表。

---

## Phase 0：修正当前工作状态

### 0.1 检查 `build_more_macro_distributions.py`

当前这个脚本写入过程中多次中断，所以第一步不是继续新建，而是：

1. 检查脚本是否语法完整；
2. 如果缺尾部，只补尾部；
3. 如果中间缺函数，改为最小可运行版本；
4. 不再反复写入超长脚本。

目标文件：

```text
build_more_macro_distributions.py
```

验证命令：

```bash
py -m py_compile build_more_macro_distributions.py
```

通过后再运行。

---

## Phase 1：构建更多 Kalshi 宏观分布

### 1.1 已完成数据

| 数据 | 文件 | 状态 |
|---|---|---|
| FFR 利率水平 | `out_csv/kalshi_ffr_distributions_daily_v2.csv` | 已完成 |
| FEDDECISION 政策动作 | `out_csv/kalshi_feddecision_distributions_daily.csv` | 已完成 |
| CPI YoY | `out_csv/kalshi_cpi_distributions_daily.csv` | 已完成 |
| 合并 FFR + FEDDECISION | `out_csv/kalshi_combined_distributions_daily.csv` | 已完成 |
| 真实 ETF 价格 | `out_csv/TLT_yahoo_daily.csv` 等 | 已完成 |
| Fed target upper | `out_csv/DFEDTARU_fred_daily.csv` | 已完成 |

---

### 1.2 需要新增的 Kalshi 宏观分布

#### A. Core CPI

市场示例：

```text
KXCPICOREYOY-25NOV-T3.5
KXCPICOREYOY-25NOV-T3.4
```

含义：

```text
核心 CPI YoY 是否高于某个 strike
```

方法：

- above-threshold 累积概率；
- 按 `release_date = close_time.date()` 聚类；
- 对同一发布日期的多个 strike 做 CDF 差分；
- 输出每日分布。

输出文件：

```text
out_csv/kalshi_corecpi_distributions_daily.csv
```

字段：

```text
series
release_date
trade_date
days_to_release
mean
median
mode
std
num_strikes
```

方向解释：

```text
Core CPI 预期下降 -> 看多长债
Core CPI 预期上升 -> 看空长债
```

---

#### B. PCE Core

市场示例：

```text
KXPCECORE-26NOV-T0.4
KXPCECORE-26NOV-T0.3
```

含义：

```text
某月核心 PCE 月环比是否高于某个 strike
```

方法：

- above-threshold；
- CDF 差分；
- 按 `release_date` 聚类。

输出文件：

```text
out_csv/kalshi_pcecore_distributions_daily.csv
```

字段：

```text
series
release_date
trade_date
days_to_release
mean
median
mode
std
num_strikes
```

方向解释：

```text
PCE Core 预期下降 -> 看多长债
PCE Core 预期上升 -> 看空长债
```

---

#### C. U3 失业率

市场示例：

```text
KXU3-25NOV-T4.7
U3-24OCT-T4.5
```

含义：

```text
失业率是否高于某个 strike
```

注意：

- 有 `KXU3` 和 `U3` 两种前缀；
- 都应该纳入；
- 同一 release date 聚类。

输出文件：

```text
out_csv/kalshi_u3_distributions_daily.csv
```

字段：

```text
series
release_date
trade_date
days_to_release
mean
median
mode
std
num_strikes
```

方向解释：

```text
U3 预期上升 -> 就业恶化 -> 看多长债
U3 预期下降 -> 就业强劲 -> 看空长债
```

---

#### D. RATECUTCOUNT 降息次数

市场示例：

```text
KXRATECUTCOUNT-26DEC31-T9
KXRATECUTCOUNT-26DEC31-T8
```

含义：

```text
到某年年底 Fed 会降息 N 次吗？
```

注意：

这不是 above-threshold 市场，而是离散分类市场，所以不能 CDF 差分。

处理方式：

1. 同一 target date 聚类；
2. 对每个 `Tn` 读取当天最后 `yes_price`；
3. 将所有 `yes_price` 归一化成离散概率分布；
4. 计算：

```text
expected_count
median_count
mode_count
std_count
```

输出文件：

```text
out_csv/kalshi_ratecutcount_distributions_daily.csv
```

字段：

```text
series
target_date
trade_date
days_to_target
expected_count
median_count
mode_count
std_count
num_counts
```

方向解释：

```text
预期降息次数上升 -> 看多长债
预期降息次数下降 -> 看空长债
```

---

## Phase 2：构建宏观日频因子面板

目标文件：

```text
build_macro_factor_panel.py
```

输出文件：

```text
out_csv/kalshi_macro_factor_panel_daily.csv
```

### 2.1 面板索引

以真实 ETF 可交易日为主，比如 `TLT_yahoo_daily.csv` 的交易日：

```text
trade_date
```

合并所有 Kalshi 宏观预测。

---

### 2.2 因子字段

最终面板至少包含：

```text
trade_date

# FFR / FOMC
ffr_mode
ffr_gap_bps
ffr_mode_delta_bps
feddecision_expected_change_bps
feddecision_prob_cut
feddecision_prob_hike

# Inflation
cpi_mode
cpi_mode_delta
corecpi_mode
corecpi_mode_delta
pcecore_mode
pcecore_mode_delta

# Labor
u3_mode
u3_mode_delta

# Policy path
ratecut_expected_count
ratecut_expected_count_delta

# Asset prices
TLT_ret_next
EDV_ret_next
ZROZ_ret_next
GOVZ_ret_next
IEF_ret_next
SHY_ret_next
```

---

### 2.3 对齐规则

#### 对 FOMC 类预测

使用最近未来 FOMC：

```text
每个 trade_date 选择 days_to_fomc >= 0 且最小的 FOMC
```

#### 对 CPI/PCE/U3 类预测

使用最近未来 release：

```text
每个 trade_date 选择 days_to_release >= 0 且最小的 release
```

#### 对 RATECUTCOUNT

使用最近目标年末合约：

```text
每个 trade_date 选择 days_to_target >= 0 且最近 target_date
```

---

## Phase 3：构造单因子信号

目标文件：

```text
build_macro_signals.py
```

或者直接并入回测脚本。

### 3.1 FFR gap signal

```text
ffr_gap_bps = (ffr_mode - current_ffr_upper) * 100
```

方向：

```text
ffr_gap_bps < 0 -> 市场预期降息 -> 做多长债
ffr_gap_bps > 0 -> 市场预期加息 -> 做空长债
```

标准化信号：

```text
signal_ffr = -z(ffr_gap_bps)
```

---

### 3.2 FEDDECISION signal

```text
signal_feddecision = -z(expected_change_bps)
```

解释：

```text
expected_change_bps 越负，越看多长债
```

---

### 3.3 CPI / Core CPI / PCE signal

用 revision，而不是绝对水平：

```text
cpi_revision = cpi_mode.diff()
corecpi_revision = corecpi_mode.diff()
pcecore_revision = pcecore_mode.diff()
```

方向：

```text
通胀预期下修 -> 看多长债
```

所以：

```text
signal_cpi = -z(cpi_revision)
signal_corecpi = -z(corecpi_revision)
signal_pcecore = -z(pcecore_revision)
```

---

### 3.4 U3 signal

```text
u3_revision = u3_mode.diff()
```

方向：

```text
失业率预期上修 -> 看多长债
```

所以：

```text
signal_u3 = z(u3_revision)
```

---

### 3.5 RATECUTCOUNT signal

```text
ratecut_revision = expected_count.diff()
```

方向：

```text
预期降息次数上升 -> 看多长债
```

所以：

```text
signal_ratecut = z(ratecut_revision)
```

---

## Phase 4：多因子合成信号

目标输出：

```text
macro_score
```

### 4.1 等权版本

先不要机器学习，避免过拟合。

```text
macro_score =
    0.25 * signal_ffr
  + 0.15 * signal_feddecision
  + 0.20 * signal_inflation
  + 0.20 * signal_labor
  + 0.20 * signal_ratepath
```

其中：

```text
signal_inflation = average(signal_cpi, signal_corecpi, signal_pcecore)
signal_labor = signal_u3
signal_ratepath = signal_ratecut
```

如果某个因子当天缺失，则对可用因子重新归一化。

---

### 4.2 纯 Kalshi revision 版本

为了避免 `ffr_gap_bps` 这种依赖当前 target rate 的结构，也做一个纯 revision 版本：

```text
macro_revision_score =
    average(
        -ffr_mode_delta,
        -feddecision_expected_change_delta,
        -cpi_mode_delta,
        -corecpi_mode_delta,
        -pcecore_mode_delta,
        +u3_mode_delta,
        +ratecut_expected_count_delta
    )
```

---

## Phase 5：真实 ETF 回测

目标文件：

```text
backtest_kalshi_macro_composite_etf.py
```

使用真实 ETF：

```text
TLT
EDV
ZROZ
GOVZ
IEF
SHY
```

### 5.1 策略规则

测试两类策略。

#### A. Threshold 策略

```text
if macro_score > threshold:
    long ETF
elif macro_score < -threshold:
    short ETF
else:
    flat
```

测试阈值：

```text
0.25, 0.5, 0.75, 1.0
```

#### B. Continuous 策略

```text
position = clip(macro_score / 2, -1, 1)
```

---

### 5.2 频率

测试：

```text
daily
weekly
```

周频版本：

```text
每周五或每周第一个可交易日更新仓位
```

---

### 5.3 成本

先统一：

```text
transaction_cost = 1bp * turnover
```

后续可扩展：

```text
TLT: 1bp
EDV/ZROZ/GOVZ: 2-3bp
```

---

### 5.4 输出指标

每个策略输出：

```text
n_days
trading_days
position_changes
total_return
annual_return
annual_vol
sharpe
max_drawdown
win_rate_active
turnover
avg_position_abs
```

输出文件：

```text
out_csv/kalshi_macro_composite_etf_grid.csv
out_csv/kalshi_macro_composite_best_by_symbol.csv
out_csv/kalshi_macro_composite_TLT_nav.png
```

---

## Phase 6：稳健性与防过拟合

这个必须做，否则很容易“调参调出来”。

### 6.1 样本内 / 样本外切分

建议切分：

```text
Train: 2022-01-01 到 2024-12-31
Test:  2025-01-01 之后
```

但注意 2025 后很多 Kalshi 预测是未来会议，对资产价格已有数据到 2026-05，所以可以测试。

输出：

```text
train_sharpe
test_sharpe
train_return
test_return
```

---

### 6.2 参数稳健性

不是只看最优，而是看矩阵：

```text
threshold × rebalance_frequency × ETF
```

如果只有一个点好，说明不稳健。

---

### 6.3 单因子 vs 多因子

比较：

```text
FFR only
Inflation only
Labor only
RatePath only
Composite
```

如果 Composite 只比单因子好一点，但更复杂，需要谨慎。

---

### 6.4 与基准比较

基准：

```text
Buy & hold TLT
Buy & hold EDV
FFR gap only
Simple duration timing using DFEDTARU changes
```

---

## Phase 7：结果解释与报告

最终报告文件：

```text
KALSHI_MACRO_STRATEGY_REPORT.md
```

报告结构：

1. 数据来源；
2. 市场结构；
3. 因子定义；
4. 回测方法；
5. 单因子表现；
6. 多因子表现；
7. 稳健性检验；
8. 局限性；
9. 下一步。

---

## 执行顺序

### Step 1

修复并运行：

```text
build_more_macro_distributions.py
```

产出：

```text
kalshi_pcecore_distributions_daily.csv
kalshi_u3_distributions_daily.csv
kalshi_corecpi_distributions_daily.csv
kalshi_ratecutcount_distributions_daily.csv
```

### Step 2

构建：

```text
build_macro_factor_panel.py
```

产出：

```text
kalshi_macro_factor_panel_daily.csv
```

### Step 3

运行多因子回测：

```text
backtest_kalshi_macro_composite_etf.py
```

产出：

```text
kalshi_macro_composite_etf_grid.csv
kalshi_macro_composite_best_by_symbol.csv
kalshi_macro_composite_TLT_nav.png
```

### Step 4

做稳健性检验：

```text
analyze_macro_strategy_robustness.py
```

产出：

```text
kalshi_macro_composite_train_test.csv
kalshi_macro_composite_factor_ablation.csv
kalshi_macro_composite_robustness_heatmap.png
```

### Step 5

写最终报告：

```text
KALSHI_MACRO_STRATEGY_REPORT.md
```

---

## 当前应该避免的事

1. 不再把 18 次事件窗口结果当结论；
2. 不再用 DGS20 久期近似作为主回测；
3. 不再只看最优参数；
4. 不直接上机器学习；
5. 不把未来 FOMC 已知结果错误用于历史交易信号；
6. 不混淆 Kalshi 预测日期和事件发布日期。

---

## 当前最重要的判断

长债不是只由下一次 FOMC 定价，而是由未来短利率路径、通胀、就业和增长风险共同定价。

所以接下来应该从：

```text
单一 FFR 信号
```

升级成：

```text
Kalshi macro composite signal
```

这才是更合理的策略研究方向。

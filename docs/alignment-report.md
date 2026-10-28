# Kalshi 数据对齐进展报告

## 已完成工作

### 1. Kalshi 数据结构识别 ✅
- **Ticker 格式**: `KXFED-25MAY-T4.50`
  - `KXFED`: Fed Funds Rate 市场
  - `25MAY`: 2025年5月 FOMC 会议
  - `T4.50`: Strike = 4.50%（累积概率：FFR ≥ 4.50%）
  
- **数据量**:
  - 找到 742 个 Fed 相关市场
  - 其中 499 个是利率市场（包含 strike）
  - 122,625 笔交易记录
  - 覆盖 46 个 FOMC 事件（2021-2027）

### 2. 分布构建（日频）✅
- **方法**: 严格按照论文 Section 3
  - 从 trades 提取每日最后一笔交易的 `yes_price`（累积概率）
  - 差分得到边际概率（PDF）
  - 计算 mean/median/mode/variance/skewness
  
- **结果**:
  - 成功构建 **3,368 个日频分布**
  - 覆盖 **38 个 FOMC 事件**
  - 时间范围: 2021-12-29 到 2025-11-24
  - 平均每个事件有 89 天的交易数据

### 3. 数据质量验证 ✅
- **统计摘要**:
  - Mean: 4.16% ± 1.30%（合理范围）
  - Mode: 4.17% ± 1.30%
  - Std: 0.34%（平均不确定性）
  - 无异常值（所有 mean 在 0-10% 范围内）

- **示例**: 2024-MAR FOMC
  - 98 天交易数据
  - Mode 从 4.62% 逐渐上升到 5.62%
  - 不确定性随 FOMC 临近而下降（符合论文预期）

---

## 关键差异对齐

### 论文方法 vs 当前 Pipeline

| 维度 | 论文（Kalshi） | 当前 Pipeline（Polymarket） | 状态 |
|------|----------------|----------------------------|------|
| **数据结构** | 多个 strike 组成分布 | 单一概率 | ✅ 已对齐 |
| **预测指标** | Mode/Median/Mean | 简单信号聚合 | ✅ 已实现 |
| **频率** | 日频 + 日内高频 | 分钟级 | ✅ 日频完成 |
| **分布构建** | CDF 差分 → PDF | N/A | ✅ 已实现 |

---

## 下一步工作

### ✅ Phase 1.5: 提前 N 天有效性评估（策略视角）

我们已经完成了“严格提前 N 天取样 + topN/stack 信号 + selective reject + quantize +（可选）median regression”的网格搜索评估，
并输出了按 `window ∈ {1,3,5,7,10}` 的 MAE/RMSE 矩阵与信号选择矩阵。

详见策略报告：`KALSHI_STRATEGY_REPORT.md`（仓库根目录）。

### Phase 1: 预测精度评估（对标论文 Table 3）
**目标**: 验证 Kalshi mode 是否优于 Fed Funds Futures

**任务**:
1. 获取实际 FOMC 决策结果（realized FFR）
2. 计算 MAE/RMSE:
   - Kalshi mode vs realized
   - Kalshi median vs realized
   - Kalshi mean vs realized
3. 对比 Fed Funds Futures（如果有数据）
4. Diebold-Mariano 检验

**输出**: `08_forecast_evaluation.py` + 结果表格

---

### Phase 2: 频率选择（日频 vs 周频 vs 月频）
**论文使用**:
- **日频**: 预测精度评估（Table 3, Figure 1）
- **日内高频**: 事件研究（Table 4, Figure 6）

**建议**:
- **主策略**: 日频（已完成）
  - 理由: 论文的 MAE/RMSE 对比是日频
  - 与 ZT 期货日收盘价对齐
  - 数据量充足（3,368 个观测）

- **事件研究**: 日内高频（待实现）
  - 理由: 捕捉 CPI/FOMC 发布后 1 小时内的反应
  - 需要小时级聚合
  - 仅用于 Section 7 的事件研究

**决策**: 先用日频完成预测评估，再考虑是否需要日内高频

---

### Phase 3: 事件研究（对标论文 Table 4）
**目标**: 分析宏观新闻对分布各阶矩的影响

**回归模型**:
```
Δmoment_t = β0 + β1 * Surprise_t + ε_t
```

**任务**:
1. 获取宏观数据发布时间和 surprise:
   - CPI (actual - Bloomberg consensus)
   - NFP (非农就业)
   - FOMC 声明
2. 计算发布日的分布变化（Δmean, Δvariance, Δskewness）
3. OLS 回归（robust SE）
4. 对比论文 Table 4 的系数

**输出**: `09_event_study.py` + 回归结果表

---

### Phase 4: 与 ZT 期货整合
**目标**: 将 Kalshi 预测信号整合到交易策略

**方法**:
1. 将 Kalshi mode 作为"市场预期利率"
2. 计算 ZT 期货隐含利率
3. 构建信号:
   - `signal = Kalshi_mode - ZT_implied_rate`
   - 如果 signal > threshold，做多/做空 ZT
4. 回测策略表现

**输出**: 新增策略模块

---

## 文件清单

### 已创建
- `search_fed_markets.py`: 搜索 Fed 市场
- `analyze_fed_tickers.py`: 分析 ticker 结构
- `build_kalshi_dist.py`: 构建日频分布 ⭐
- `validate_kalshi_dist.py`: 验证分布质量
- `out_csv/kalshi_fed_markets.csv`: 742 个 Fed 市场
- `out_csv/kalshi_ffr_distributions_daily.csv`: 3,368 个日频分布 ⭐
- `out_csv/kalshi_event_summary.csv`: 事件统计摘要
- `out_csv/kalshi_2024mar_validation.png`: 可视化验证

### 待创建
- `pipeline/08_forecast_evaluation.py`: 预测精度评估
- `pipeline/09_event_study.py`: 事件研究
- `pipeline/10_kalshi_zt_integration.py`: 与 ZT 期货整合

---

## 关键发现

1. **数据质量良好**: 
   - 无异常值
   - 分布参数在合理范围内
   - 时间序列连续性好

2. **流动性充足**:
   - 平均每个事件 89 天交易数据
   - 平均 3.3 个 strikes（足够构建分布）

3. **符合论文预期**:
   - 不确定性随 FOMC 临近而下降
   - Mode 是最稳定的预测指标

---

## 建议

**立即行动**:
1. ✅ 完成 Phase 1（预测精度评估）
2. 确认频率选择（建议：日频）
3. 决定是否需要 Phase 3（事件研究）

**优先级**:
- **高**: Phase 1（验证 Kalshi 预测能力）
- **中**: Phase 4（整合到交易策略）
- **低**: Phase 3（学术研究，非必需）

---

生成时间: 2025-01-XX

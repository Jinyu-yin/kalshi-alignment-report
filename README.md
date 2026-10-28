# Kalshi Alignment Report

> 把 Kalshi 预测市场的多档位（strike）合约还原成**宏观变量的概率分布**，并对齐到国债 ETF 的可交易信号上。

![status](https://img.shields.io/badge/status-research-blue) ![python](https://img.shields.io/badge/python-3.10%2B-3776ab) ![license](https://img.shields.io/badge/license-private-lightgrey)

---

## 这是什么

一份**研究过程记录 + 数据对齐脚本集**。目标不是"预测某个合约会不会中"，而是回答一个更有交易价值的问题：

> 市场当前隐含的**联邦基金利率分布**长什么样？它的形状变化（位移 / 收窄 / 偏斜）能不能提前解释长债 ETF 的走势？

参考范式来自一篇以 Kalshi 为数据源的学术论文：论文用同一到期日、不同 strike 的一揽子合约（累计概率）反推出利率的完整概率密度，再用众数（mode）作为点预测，与联邦基金期货做精度对比。

本仓库记录的是把原有 Polymarket 单一概率 pipeline **迁移并校准到 Kalshi 数据结构**的过程、验证结果与后续执行计划。

---

## 核心结论（已完成部分）

| 项目 | 结果 |
|---|---|
| Fed 相关市场 | 742 个（其中 499 个带 strike 的利率市场） |
| 交易记录 | 122,625 笔 |
| 覆盖 FOMC 事件 | 46 个（2021–2027） |
| 成功构建日频分布 | **3,368 个**，覆盖 **38 个 FOMC 事件** |
| 时间范围 | 2021-12-29 ~ 2025-11-24 |
| 平均每个事件可用交易日 | 89 天 |

数据质量：均值 4.16% ± 1.30%，标准差 0.34%，无越界值；且**不确定性随 FOMC 临近单调收窄**，与论文结论一致。

---

## 方法论：CDF 差分还原 PDF

Kalshi 的利率合约是**累积概率**合约（"FFR ≥ 4.50%"），ticker 形如：

```
KXFED-25MAY-T4.50
 │      │      └── Strike = 4.50%
 │      └───────── 2025 年 5 月 FOMC
 └──────────────── Fed Funds Rate 市场
```

因此还原分布的步骤是：

1. 取每个交易日的**最后一笔成交** `yes_price`，作为该 strike 的当日累积概率 `F(x)`；
2. 按 strike 升序排列，**相邻差分**得到边际概率（PDF）；
3. 由 PDF 计算 `mean / median / mode / variance / skewness`。

这里刻意只用"当日收盘时的信息"，避免用到未来数据——这是后续做策略评估时**时点一致性（PIT）**的前提。

---

## 目录结构

```
kalshi-alignment-report/
├── docs/
│   ├── alignment-report.md        # 数据对齐进展报告（本仓库主线文档）
│   ├── macro-execution-plan.md    # 宏观复合策略的分阶段执行计划
│   └── pipeline-readme.md         # 原始 8-Step pipeline 说明（迁移前版本）
└── scripts/
    ├── analyze_fed_tickers.py            # 解析 ticker 结构，识别 strike
    ├── analyze_all_fed_markets.py        # 全量 Fed 市场盘点
    ├── analyze_macro_indicators.py       # CPI / 失业率等宏观市场分析
    ├── build_kalshi_dist_v2.py           # ⭐ 日频分布构建（CDF → PDF）
    ├── backtest_kalshi_20y.py            # 长周期回测（利率水平信号）
    ├── backtest_kalshi_20y_event.py      # 事件驱动版本回测
    ├── backtest_kalshi_dailyfreq_etf.py  # 日频信号 → ETF
    └── backtest_kalshi_tradeable_etf.py  # 可交易标的（TLT / EDV / ZROZ / GOVZ）
```

> 脚本按"分析 → 构分布 → 回测"的顺序执行，路径约定为 `out_csv/` 作为中间产物目录。

---

## 快速开始

```bash
pip install pandas numpy requests matplotlib pyarrow
```

```bash
# 1. 盘点市场
python scripts/analyze_fed_tickers.py

# 2. 构建日频分布（核心）
python scripts/build_kalshi_dist_v2.py

# 3. 回测
python scripts/backtest_kalshi_tradeable_etf.py
```

预期中间产物：

```
out_csv/
├── kalshi_fed_markets.csv                  # 742 个 Fed 市场
├── kalshi_ffr_distributions_daily.csv      # 3,368 个日频分布
├── kalshi_event_summary.csv                # 事件级统计
└── TLT_yahoo_daily.csv ...                 # 真实 ETF 价格
```

---

## 复合宏观因子的设计思路

单一 FFR 分布只能回答"市场觉得利率在哪"，但长债的方向由**四个方向**共同决定：

```
看多长债 = Fed 更鸽 + 通胀预期下行 + 就业恶化 + 未来降息路径增加
```

因此执行计划（见 `docs/macro-execution-plan.md`）把 Kalshi 拆成多类市场分别建模：

| 维度 | 数据来源 | 用途 |
|---|---|---|
| 利率水平 | `KXFED`（多 strike） | 分布位移 |
| 政策动作 | `KXFEDDECISION` | 加息/降息/不动的概率 |
| 通胀 | CPI YoY 市场 | 通胀预期 |
| 就业 | 失业率市场 | 增长动能 |

再合成 → 单因子回测 → 多因子合成回测 → 稳健性检验。

---

## 已知限制

- **不是生产交易系统**：回测未计入交易成本、滑点与保证金占用。
- **strike 密度不均**：平均每个事件仅 3.3 个 strike，尾部概率的差分噪声较大。
- **流动性分层**：临近到期日的合约成交活跃，远月合约稀疏，需做质量过滤。
- **众数对分箱敏感**：mode 依赖 strike 网格，跨事件比较时建议同时看 median。
- 数据获取依赖 Kalshi 公开 API，历史深度有限。

---

## 后续路线

- [x] 数据结构识别与分布构建
- [x] 日频 / 事件频回测框架
- [ ] Phase 1：预测精度评估（MAE / RMSE + Diebold-Mariano 检验，对标论文 Table 3）
- [ ] Phase 3：事件研究（宏观 surprise → 分布各阶矩变化）
- [ ] Phase 4：与 ZT 期货 / 长债 ETF 的整合信号

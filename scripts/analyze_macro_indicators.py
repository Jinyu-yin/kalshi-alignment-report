"""
分析其他宏观指标市场的数据量和结构
"""
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

fed = pd.read_csv('out_csv/kalshi_fed_markets.csv', encoding='utf-8-sig')

print("=== 宏观指标市场分析 ===\n")

# 1. CPI 市场
print("1. CPI（消费者物价指数）市场")
print("=" * 60)

cpi_yoy = fed[fed['ticker'].str.match(r'^(?:KX)?CPIYOY-', na=False)]
cpi_core_yoy = fed[fed['ticker'].str.match(r'^(?:KX)?CPICOREYOY-', na=False)]

print(f"\nCPI YoY（年度通胀率）: {len(cpi_yoy)} 个市场")
if len(cpi_yoy) > 0:
    cpi_yoy['close_time'] = pd.to_datetime(cpi_yoy['close_time'])
    print(f"  时间范围: {cpi_yoy['close_time'].min().date()} 到 {cpi_yoy['close_time'].max().date()}")
    print(f"  唯一发布日期: {cpi_yoy['close_time'].dt.date.nunique()} 个")
    print(f"  示例 ticker: {cpi_yoy['ticker'].head(3).tolist()}")
    print(f"  示例 title: {cpi_yoy['title'].iloc[0][:100]}")

print(f"\nCPI Core YoY（核心通胀率）: {len(cpi_core_yoy)} 个市场")
if len(cpi_core_yoy) > 0:
    cpi_core_yoy['close_time'] = pd.to_datetime(cpi_core_yoy['close_time'])
    print(f"  时间范围: {cpi_core_yoy['close_time'].min().date()} 到 {cpi_core_yoy['close_time'].max().date()}")
    print(f"  唯一发布日期: {cpi_core_yoy['close_time'].dt.date.nunique()} 个")
    print(f"  示例 ticker: {cpi_core_yoy['ticker'].head(3).tolist()}")
    print(f"  示例 title: {cpi_core_yoy['title'].iloc[0][:100]}")

# 2. PCE 市场
print("\n\n2. PCE（个人消费支出价格指数）市场")
print("=" * 60)

pce_core = fed[fed['ticker'].str.startswith('KXPCECORE')]

print(f"\nPCE Core（核心 PCE）: {len(pce_core)} 个市场")
if len(pce_core) > 0:
    pce_core['close_time'] = pd.to_datetime(pce_core['close_time'])
    print(f"  时间范围: {pce_core['close_time'].min().date()} 到 {pce_core['close_time'].max().date()}")
    print(f"  唯一发布日期: {pce_core['close_time'].dt.date.nunique()} 个")
    print(f"  示例 ticker: {pce_core['ticker'].head(3).tolist()}")
    print(f"  示例 title: {pce_core['title'].iloc[0][:100]}")
    
    # 检查是否有 strike
    print(f"\n  Strike 分布:")
    sample_date = pce_core['close_time'].dt.date.value_counts().index[0]
    sample_strikes = pce_core[pce_core['close_time'].dt.date == sample_date]
    print(f"    示例日期 {sample_date}: {len(sample_strikes)} 个 strikes")
    for _, row in sample_strikes.head(5).iterrows():
        print(f"      {row['ticker']}")

# 3. 失业率市场
print("\n\n3. U3（失业率）市场")
print("=" * 60)

u3 = fed[fed['ticker'].str.match(r'^(?:KX)?U3-', na=False)]

print(f"\nU3 失业率: {len(u3)} 个市场")
if len(u3) > 0:
    u3['close_time'] = pd.to_datetime(u3['close_time'])
    print(f"  时间范围: {u3['close_time'].min().date()} 到 {u3['close_time'].max().date()}")
    print(f"  唯一发布日期: {u3['close_time'].dt.date.nunique()} 个")
    print(f"  示例 ticker: {u3['ticker'].head(3).tolist()}")
    print(f"  示例 title: {u3['title'].iloc[0][:100]}")
    
    # 检查 strike 分布
    print(f"\n  Strike 分布:")
    sample_date = u3['close_time'].dt.date.value_counts().index[0]
    sample_strikes = u3[u3['close_time'].dt.date == sample_date]
    print(f"    示例日期 {sample_date}: {len(sample_strikes)} 个 strikes")

# 4. 其他有趣的市场
print("\n\n4. 其他宏观市场")
print("=" * 60)

# Powell 提及市场
powell = fed[fed['ticker'].str.startswith('KXPOWELLMENTION')]
print(f"\nPowell 讲话提及市场: {len(powell)} 个")
if len(powell) > 0:
    print(f"  示例: {powell['title'].iloc[0][:120]}")

# 降息次数市场
rate_cut_count = fed[fed['ticker'].str.startswith('KXRATECUTCOUNT')]
print(f"\n降息次数预测市场: {len(rate_cut_count)} 个")
if len(rate_cut_count) > 0:
    rate_cut_count['close_time'] = pd.to_datetime(rate_cut_count['close_time'], format='mixed')
    print(f"  时间范围: {rate_cut_count['close_time'].min().date()} 到 {rate_cut_count['close_time'].max().date()}")
    print(f"  示例 ticker: {rate_cut_count['ticker'].head(3).tolist()}")
    print(f"  示例 title: {rate_cut_count['title'].iloc[0][:100]}")

# 政府关门市场
gov_shut = fed[fed['ticker'].str.startswith('KXGOVSHUTLENGTH')]
print(f"\n政府关门市场: {len(gov_shut)} 个")

print("\n\n" + "=" * 60)
print("=== 数据可用性总结 ===")
print("=" * 60)

summary = [
    ("FFR 利率水平", 487, "✅ 已使用", "预测 FOMC 后的利率水平"),
    ("FEDDECISION", 200, "✅ 已使用", "预测 FOMC 的政策动作"),
    ("CPI YoY", len(cpi_yoy), "⭐ 推荐", "通胀预期，影响 FOMC 决策"),
    ("CPI Core YoY", len(cpi_core_yoy), "⭐ 推荐", "核心通胀，Fed 重点关注"),
    ("PCE Core", len(pce_core), "⭐ 推荐", "Fed 首选通胀指标"),
    ("U3 失业率", len(u3), "⭐ 推荐", "劳动力市场，影响货币政策"),
    ("降息次数", len(rate_cut_count), "🔸 可选", "政策路径预期"),
    ("Powell 讲话", len(powell), "🔸 可选", "市场情绪指标"),
]

print(f"\n{'指标':<20} {'市场数':<10} {'状态':<15} {'用途'}")
print("-" * 80)
for name, count, status, usage in summary:
    print(f"{name:<20} {count:<10} {status:<15} {usage}")

print("\n\n=== 论文中使用的指标 ===")
print("论文 Table 4（事件研究）使用了:")
print("  1. CPI 发布 - 分析通胀意外对 FFR 预期的影响")
print("  2. NFP（非农就业）发布 - 分析就业数据对 FFR 预期的影响")
print("  3. FOMC 声明 - 分析政策声明对市场预期的影响")

print("\n\n=== 建议的扩展优先级 ===")
print("\n优先级 1（高价值，易实现）:")
print("  ✅ CPI/PCE 市场 - 可以做事件研究（复现论文 Table 4）")
print("     - 构建通胀预期分布")
print("     - 分析 CPI surprise 对 FFR 预期的影响")
print("     - 回归: Δ(FFR mode) = β * CPI_surprise")

print("\n优先级 2（补充信号）:")
print("  ✅ U3 失业率市场 - 劳动力市场预期")
print("     - 与 FFR 预期的关系（菲利普斯曲线）")
print("     - 双重使命：通胀 + 就业")

print("\n优先级 3（策略增强）:")
print("  🔸 降息次数市场 - 政策路径预期")
print("     - 市场对未来 6-12 个月的政策路径预期")
print("     - 可以构建收益率曲线预期")

print("\n\n要我开始处理哪个指标？")

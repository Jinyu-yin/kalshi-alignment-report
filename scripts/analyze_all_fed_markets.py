"""
分析所有可用的 Fed 相关市场
"""
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

fed = pd.read_csv('out_csv/kalshi_fed_markets.csv', encoding='utf-8-sig')

print("=== 所有 Fed 相关市场分析 ===\n")
print(f"总市场数: {len(fed)}\n")

# 1. FFR 利率市场（我们已经用的）
ffr_markets = fed[fed['ticker'].str.match(r'^(?:KX)?FED-\d{2}[A-Z]{3}-T\d', na=False)]
print(f"1. FFR 利率市场（已使用）: {len(ffr_markets)}")
print(f"   示例: {ffr_markets['ticker'].head(3).tolist()}")
print(f"   Title: {ffr_markets['title'].iloc[0][:100]}\n")

# 2. FEDDECISION 市场（可能是二元决策市场）
fed_decision = fed[fed['ticker'].str.startswith('FEDDECISION')]
print(f"2. FEDDECISION 市场: {len(fed_decision)}")
if len(fed_decision) > 0:
    print(f"   示例: {fed_decision['ticker'].head(3).tolist()}")
    print(f"   Title: {fed_decision['title'].iloc[0][:100]}\n")

# 3. KXFEDDECISION 市场
kx_fed_decision = fed[fed['ticker'].str.startswith('KXFEDDECISION')]
print(f"3. KXFEDDECISION 市场: {len(kx_fed_decision)}")
if len(kx_fed_decision) > 0:
    print(f"   示例: {kx_fed_decision['ticker'].head(3).tolist()}")
    print(f"   Title: {kx_fed_decision['title'].iloc[0][:100]}\n")

# 4. 失业率市场
u3_markets = fed[fed['ticker'].str.match(r'^(?:KX)?U3-', na=False)]
print(f"4. U3 失业率市场: {len(u3_markets)}")
if len(u3_markets) > 0:
    print(f"   示例: {u3_markets['ticker'].head(3).tolist()}")
    print(f"   Title: {u3_markets['title'].iloc[0][:100]}\n")

# 5. CPI 市场
cpi_markets = fed[fed['ticker'].str.match(r'^(?:KX)?CPI', na=False)]
print(f"5. CPI 市场: {len(cpi_markets)}")
if len(cpi_markets) > 0:
    print(f"   示例: {cpi_markets['ticker'].head(3).tolist()}")
    print(f"   Title: {cpi_markets['title'].iloc[0][:100]}\n")

# 6. PCE 市场
pce_markets = fed[fed['ticker'].str.startswith('KXPCECORE')]
print(f"6. PCE 核心通胀市场: {len(pce_markets)}")
if len(pce_markets) > 0:
    print(f"   示例: {pce_markets['ticker'].head(3).tolist()}")
    print(f"   Title: {pce_markets['title'].iloc[0][:100]}\n")

# 7. Powell 提及市场
powell_markets = fed[fed['ticker'].str.startswith('KXPOWELLMENTION')]
print(f"7. Powell 提及市场: {len(powell_markets)}")
if len(powell_markets) > 0:
    print(f"   示例: {powell_markets['ticker'].head(3).tolist()}")
    print(f"   Title: {powell_markets['title'].iloc[0][:100]}\n")

# 8. 降息次数市场
rate_cut_markets = fed[fed['ticker'].str.startswith('KXRATECUTCOUNT')]
print(f"8. 降息次数市场: {len(rate_cut_markets)}")
if len(rate_cut_markets) > 0:
    print(f"   示例: {rate_cut_markets['ticker'].head(3).tolist()}")
    print(f"   Title: {rate_cut_markets['title'].iloc[0][:100]}\n")

print("\n=== 建议 ===")
print("1. 优先级 1（必须）: FFR 利率市场（已完成）")
print("2. 优先级 2（推荐）: FEDDECISION 市场 - 可能提供额外的利率预期信息")
print("3. 优先级 3（可选）: CPI/PCE 市场 - 用于事件研究")
print("4. 优先级 4（可选）: 降息次数市场 - 提供政策路径预期")

# 检查 FEDDECISION 是否有 strike
print("\n=== 检查 FEDDECISION 市场结构 ===")
if len(fed_decision) > 0:
    print("FEDDECISION 示例:")
    for _, row in fed_decision.head(10).iterrows():
        print(f"  {row['ticker']}: {row['title'][:120]}")

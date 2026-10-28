"""
分析 Fed 市场的 ticker 结构
"""
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv('out_csv/kalshi_fed_markets.csv', encoding='utf-8-sig')

# 筛选真正的 Fed 决策市场
fed_only = df[df['ticker'].str.startswith('FED') | df['ticker'].str.startswith('KXFED')]
print(f'Fed decision markets: {len(fed_only)}')

print('\n=== Sample Fed Decision Markets ===')
for _, row in fed_only.head(50).iterrows():
    print(f"\nTicker: {row['ticker']}")
    print(f"  Event: {row['event_ticker']}")
    print(f"  Title: {row['title'][:150]}")
    print(f"  Status: {row['status']}")
    print(f"  Created: {row['created_time']}")

# 分析 ticker 结构
print('\n\n=== Ticker Structure Analysis ===')
fed_only['ticker_parts'] = fed_only['ticker'].str.split('-')
fed_only['num_parts'] = fed_only['ticker_parts'].apply(len)
print(f"Ticker parts distribution:")
print(fed_only['num_parts'].value_counts())

print('\n\nSample ticker breakdowns:')
for _, row in fed_only.head(20).iterrows():
    parts = row['ticker'].split('-')
    print(f"{row['ticker']}: {parts}")

# 查找包含 strike/rate 信息的 ticker
print('\n\n=== Looking for rate/strike patterns ===')
rate_markets = fed_only[fed_only['ticker'].str.contains('T\d+', regex=True)]
print(f"Markets with T-pattern (potential strikes): {len(rate_markets)}")
if len(rate_markets) > 0:
    print('\nSample:')
    for _, row in rate_markets.head(20).iterrows():
        print(f"  {row['ticker']}: {row['title'][:100]}")

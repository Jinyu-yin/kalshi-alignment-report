"""
重新构建 Kalshi FFR 分布 - 使用正确的 FOMC 会议日期聚类
"""
import pandas as pd
import numpy as np
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

def parse_fed_ticker(ticker):
    """解析 KXFED-25MAY-T4.50 -> (2025, 'MAY', 4.50)"""
    pattern = r'^(?:KX)?FED-(\d{2})([A-Z]{3})-T(\d+\.?\d*)$'
    match = re.match(pattern, ticker)
    if match:
        year = int('20' + match.group(1))
        month = match.group(2)
        strike = float(match.group(3))
        return year, month, strike
    return None, None, None

def calculate_moments(pdf_dict):
    """从 PDF 计算 mean/median/mode/variance/skewness"""
    if not pdf_dict or sum(pdf_dict.values()) < 0.01:
        return None
    
    strikes = np.array(list(pdf_dict.keys()))
    probs = np.array(list(pdf_dict.values()))
    probs = probs / probs.sum()
    
    mean = np.sum(strikes * probs)
    sorted_idx = np.argsort(strikes)
    cumsum = np.cumsum(probs[sorted_idx])
    median_idx = np.searchsorted(cumsum, 0.5)
    median = strikes[sorted_idx][median_idx] if median_idx < len(strikes) else strikes[sorted_idx][-1]
    mode = strikes[np.argmax(probs)]
    variance = np.sum((strikes - mean) ** 2 * probs)
    skewness = np.sum((strikes - mean) ** 3 * probs) / (variance ** 1.5) if variance > 0 else 0
    
    return {'mean': mean, 'median': median, 'mode': mode, 'variance': variance, 
            'std': np.sqrt(variance), 'skewness': skewness}

def build_pdf_from_cdf(cdf_dict):
    """从 CDF 差分得到 PDF"""
    sorted_strikes = sorted(cdf_dict.keys())
    pdf = {}
    for i in range(len(sorted_strikes) - 1):
        prob = cdf_dict[sorted_strikes[i]] - cdf_dict[sorted_strikes[i + 1]]
        if prob > 0:
            pdf[(sorted_strikes[i] + sorted_strikes[i + 1]) / 2] = prob
    return pdf

print("=== Kalshi FFR 分布构建（正确聚类版本）===\n")

# 1. 读取 markets，用 close_time 作为 FOMC 会议日期
fed_markets = pd.read_csv('out_csv/kalshi_fed_markets.csv', encoding='utf-8-sig')
fed_markets['is_rate'] = fed_markets['ticker'].str.match(r'^(?:KX)?FED-\d{2}[A-Z]{3}-T\d', na=False)
rate_markets = fed_markets[fed_markets['is_rate']].copy()
print(f"利率市场: {len(rate_markets)}")

# 解析 ticker 和 FOMC 会议日期
rate_markets[['year', 'month', 'strike']] = rate_markets['ticker'].apply(
    lambda x: pd.Series(parse_fed_ticker(x)))
rate_markets = rate_markets.dropna(subset=['year', 'month', 'strike'])

# 关键：用 close_time 作为 FOMC 会议日期
rate_markets['fomc_date'] = pd.to_datetime(rate_markets['close_time']).dt.date
rate_markets['event'] = rate_markets['fomc_date'].astype(str)

# 按 FOMC 会议日期聚类
events = rate_markets.groupby('fomc_date')['ticker'].apply(list).to_dict()
print(f"FOMC 会议: {len(events)} 个")
print(f"\n前 10 个会议:")
for i, (date, tickers) in enumerate(sorted(events.items())[:10]):
    print(f"  {date}: {len(tickers)} 个 strikes")

# 2. 读取 trades
trades_dir = Path('data/kalshi/trades')
all_ffr_tickers = set(rate_markets['ticker'].tolist())
print(f"\n扫描 trades 文件...")

ffr_trades = []
for i, f in enumerate(sorted(trades_dir.glob('*.parquet'))):
    if i % 500 == 0:
        print(f"  {i}/7214")
    try:
        df = pd.read_parquet(f)
        df_ffr = df[df['ticker'].isin(all_ffr_tickers)]
        if len(df_ffr) > 0:
            ffr_trades.append(df_ffr)
    except:
        pass

all_trades = pd.concat(ffr_trades, ignore_index=True)
print(f"\n找到 {len(all_trades)} 笔交易\n")

# 3. 构建分布（按 FOMC 会议日期聚类）
all_distributions = []

for fomc_date, event_tickers in sorted(events.items()):
    print(f"处理: {fomc_date} ({len(event_tickers)} strikes)")
    
    event_trades = all_trades[all_trades['ticker'].isin(event_tickers)].copy()
    
    if len(event_trades) == 0:
        print(f"  无交易数据")
        continue
    
    event_trades['trade_date'] = pd.to_datetime(event_trades['created_time']).dt.date
    unique_dates = sorted(event_trades['trade_date'].unique())
    
    print(f"  交易天数: {len(unique_dates)}, 从 {unique_dates[0]} 到 {unique_dates[-1]}")
    
    for trade_date in unique_dates:
        daily = event_trades[event_trades['trade_date'] == trade_date]
        cdf = {}
        
        for ticker in daily['ticker'].unique():
            last_trade = daily[daily['ticker'] == ticker].sort_values('created_time').iloc[-1]
            _, _, strike = parse_fed_ticker(ticker)
            if strike is not None:
                cdf[strike] = last_trade['yes_price']
        
        if len(cdf) >= 2:
            pdf = build_pdf_from_cdf(cdf)
            moments = calculate_moments(pdf)
            if moments:
                moments['fomc_date'] = fomc_date
                moments['trade_date'] = trade_date
                moments['days_to_fomc'] = (fomc_date - trade_date).days
                moments['num_strikes'] = len(cdf)
                all_distributions.append(moments)

# 4. 保存
df_dist = pd.DataFrame(all_distributions)
df_dist = df_dist.sort_values(['fomc_date', 'trade_date'])
df_dist.to_csv('out_csv/kalshi_ffr_distributions_daily_v2.csv', index=False)

print(f"\n\n=== 完成 ===")
print(f"总分布数: {len(df_dist)}")
print(f"FOMC 会议数: {df_dist['fomc_date'].nunique()}")
print(f"\n前 10 行:")
print(df_dist.head(10))

print(f"\n按 FOMC 会议统计:")
event_stats = df_dist.groupby('fomc_date').agg({
    'trade_date': ['min', 'max', 'count'],
    'mode': 'mean',
    'num_strikes': 'mean'
}).round(3)
print(event_stats.head(20))

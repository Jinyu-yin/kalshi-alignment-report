"""
更多交易数版本：日频/周频 Kalshi FFR 预期策略，使用真实ETF价格。

信号：每个交易日选择最近未来 FOMC 的 Kalshi FFR mode，和当天已知 Fed target upper 比较。
- gap_bps = (kalshi_mode - current_ffr_upper) * 100
- gap < -threshold: 市场预期降息 -> 做多长债 ETF
- gap > threshold: 市场预期加息 -> 做空长债 ETF

另测 revision：mode_delta 下修 -> 做多；上修 -> 做空。

目标：提高样本和交易次数，避免只有 18 次事件交易。
"""
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8")

SYMBOLS = ["TLT", "EDV", "ZROZ", "GOVZ", "IEF", "SHY"]
TCOST_BPS = 1.0


def perf_stats(ret: pd.Series, pos: pd.Series, name: str) -> dict:
    ret = ret.dropna()
    nav = (1 + ret).cumprod()
    turnover = pos.diff().abs().fillna(pos.abs())
    trades = int((turnover > 0).sum())
    if len(ret) == 0:
        return {"strategy": name, "n": 0}
    ann_ret = nav.iloc[-1] ** (252 / len(ret)) - 1
    ann_vol = ret.std() * np.sqrt(252)
    return {
        "strategy": name,
        "n": len(ret),
        "trading_days": int((pos.abs() > 0).sum()),
        "position_changes": trades,
        "total_return": nav.iloc[-1] - 1,
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": ann_ret / ann_vol if ann_vol > 0 else np.nan,
        "max_drawdown": (nav / nav.cummax() - 1).min(),
        "win_rate_active": (ret[pos.abs() > 0] > 0).mean() if (pos.abs() > 0).any() else np.nan,
    }


def nearest_fomc_daily(kalshi: pd.DataFrame) -> pd.DataFrame:
    k = kalshi.copy()
    k = k[k["days_to_fomc"] >= 0]
    k = k.sort_values(["trade_date", "days_to_fomc", "fomc_date"])
    k = k.groupby("trade_date", as_index=False).first()
    return k


def load_asset(symbol: str) -> pd.DataFrame:
    a = pd.read_csv(f"out_csv/{symbol}_yahoo_daily.csv")
    a["date"] = pd.to_datetime(a["date"]).dt.date
    a = a.sort_values("date")
    a["asset_ret_next"] = a["adj_close"].shift(-1) / a["adj_close"] - 1
    return a[["date", "adj_close", "asset_ret_next"]]


def build_base_panel(symbol: str) -> pd.DataFrame:
    kalshi = pd.read_csv("out_csv/kalshi_combined_distributions_daily.csv")
    kalshi["trade_date"] = pd.to_datetime(kalshi["trade_date"]).dt.date
    kalshi["fomc_date"] = pd.to_datetime(kalshi["fomc_date"]).dt.date
    kalshi["days_to_fomc"] = (pd.to_datetime(kalshi["fomc_date"]) - pd.to_datetime(kalshi["trade_date"])).dt.days
    k = nearest_fomc_daily(kalshi)

    ffr = pd.read_csv("out_csv/DFEDTARU_fred_daily.csv")
    ffr["date"] = pd.to_datetime(ffr["date"]).dt.date

    asset = load_asset(symbol)

    d = k.merge(ffr, left_on="trade_date", right_on="date", how="left")
    d = d.drop(columns=["date"])
    d = d.merge(asset, left_on="trade_date", right_on="date", how="inner")
    d = d.sort_values("trade_date")
    d["ffr_upper"] = d["ffr_upper"].ffill()
    d["gap_bps"] = (d["mode"] - d["ffr_upper"]) * 100
    d["mode_delta_bps"] = d["mode"].diff() * 100
    d["feddec_signal_bps"] = d["expected_change_bps"]
    return d


def position_from_signal(sig: pd.Series, threshold: float, continuous: bool = False) -> pd.Series:
    if continuous:
        return (-sig / 100.0).clip(-1, 1).fillna(0.0)
    pos = pd.Series(0.0, index=sig.index)
    pos[sig <= -threshold] = 1.0
    pos[sig >= threshold] = -1.0
    return pos


def resample_weekly_signal(d: pd.DataFrame, pos: pd.Series) -> pd.Series:
    temp = d[["trade_date"]].copy()
    temp["pos"] = pos.values
    temp["week"] = pd.to_datetime(temp["trade_date"]).dt.to_period("W-FRI")
    weekly = temp.groupby("week")["pos"].first()
    return temp["week"].map(weekly).astype(float)


def backtest(d: pd.DataFrame, pos: pd.Series) -> pd.Series:
    pos = pos.fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.abs())
    tcost = turnover * TCOST_BPS / 10000.0
    return pos * d["asset_ret_next"] - tcost


def main():
    print("=== 日频/周频真实ETF回测：更多样本与交易次数 ===\n")

    rows = []
    best_bt = None
    best_name = None

    for symbol in SYMBOLS:
        d = build_base_panel(symbol)
        print(f"{symbol}: 面板 {len(d)} 天，{d['trade_date'].min()} 到 {d['trade_date'].max()}")

        candidates = []
        for thr in [12.5, 25, 50, 75, 100]:
            candidates.append((f"{symbol}_gap_thr{thr}_daily", position_from_signal(d["gap_bps"], thr, False)))
            candidates.append((f"{symbol}_gap_thr{thr}_weekly", resample_weekly_signal(d, position_from_signal(d["gap_bps"], thr, False))))
        for thr in [5, 10, 25, 50]:
            candidates.append((f"{symbol}_revision_thr{thr}_daily", position_from_signal(d["mode_delta_bps"], thr, False)))
            candidates.append((f"{symbol}_revision_thr{thr}_weekly", resample_weekly_signal(d, position_from_signal(d["mode_delta_bps"], thr, False))))
        candidates.append((f"{symbol}_gap_cont_daily", position_from_signal(d["gap_bps"], 0, True)))
        candidates.append((f"{symbol}_gap_cont_weekly", resample_weekly_signal(d, position_from_signal(d["gap_bps"], 0, True))))

        for name, pos in candidates:
            ret = backtest(d, pos)
            stats = perf_stats(ret, pos, name)
            stats["symbol"] = symbol
            rows.append(stats)

            bt = d[["trade_date", "fomc_date", "days_to_fomc", "mode", "ffr_upper", "gap_bps", "mode_delta_bps", "adj_close", "asset_ret_next"]].copy()
            bt["position"] = pos.values
            bt["strategy_ret"] = ret.values
            bt["nav"] = (1 + bt["strategy_ret"].fillna(0)).cumprod()
            bt.to_csv(f"out_csv/dailyfreq_bt_{name}.csv", index=False)

    res = pd.DataFrame(rows).sort_values("sharpe", ascending=False)
    res.to_csv("out_csv/kalshi_dailyfreq_tradeable_etf_grid.csv", index=False)

    print("\n=== Top 20 ===")
    cols = ["strategy", "symbol", "trading_days", "position_changes", "total_return", "ann_return", "ann_vol", "sharpe", "max_drawdown", "win_rate_active"]
    print(res[cols].head(20).to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n=== 每个标的最优 ===")
    best_by_symbol = res.groupby("symbol", as_index=False).first()
    print(best_by_symbol[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    best_by_symbol.to_csv("out_csv/kalshi_dailyfreq_best_by_symbol.csv", index=False)

    # 画 TLT 最优
    tlt_best = best_by_symbol[best_by_symbol["symbol"] == "TLT"].iloc[0]["strategy"]
    bt = pd.read_csv(f"out_csv/dailyfreq_bt_{tlt_best}.csv")
    bt["trade_date"] = pd.to_datetime(bt["trade_date"])
    plt.figure(figsize=(12, 7))
    plt.plot(bt["trade_date"], bt["nav"], label=tlt_best)
    buyhold = (1 + bt["asset_ret_next"].fillna(0)).cumprod()
    plt.plot(bt["trade_date"], buyhold, label="TLT buy_hold same panel", linestyle="--", color="black", alpha=0.7)
    plt.title("Daily/Weekly Kalshi FFR Signal on TLT")
    plt.xlabel("Date")
    plt.ylabel("NAV")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("out_csv/kalshi_TLT_dailyfreq_best_nav.png", dpi=150, bbox_inches="tight")

    print("\n已保存：")
    print("  out_csv/kalshi_dailyfreq_tradeable_etf_grid.csv")
    print("  out_csv/kalshi_dailyfreq_best_by_symbol.csv")
    print("  out_csv/kalshi_TLT_dailyfreq_best_nav.png")
    print("  out_csv/dailyfreq_bt_*.csv")


if __name__ == "__main__":
    main()

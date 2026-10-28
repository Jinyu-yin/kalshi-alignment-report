"""
严谨版：使用真实可交易美债 ETF 价格回测 Kalshi FOMC 信号。

标的：
- TLT: 20+ Year Treasury Bond ETF（主回测）
- EDV/ZROZ/GOVZ: 更长久期稳健性检验
- IEF/SHY: 中短久期对照

使用 adjusted close 计算下一交易日收益。
"""
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8")

TCOST_BPS = 1.0
SYMBOLS = ["TLT", "EDV", "ZROZ", "GOVZ", "IEF", "SHY"]


def perf_stats(ret: pd.Series, name: str) -> dict:
    ret = ret.dropna()
    if len(ret) == 0:
        return {"strategy": name, "n": 0}
    nav = (1 + ret).cumprod()
    ann_ret = nav.iloc[-1] ** (252 / len(ret)) - 1
    ann_vol = ret.std() * np.sqrt(252)
    return {
        "strategy": name,
        "n": len(ret),
        "total_return": nav.iloc[-1] - 1,
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": ann_ret / ann_vol if ann_vol > 0 else np.nan,
        "max_drawdown": (nav / nav.cummax() - 1).min(),
        "win_rate": (ret > 0).mean(),
    }


def prepare_realized_with_prev():
    realized = pd.read_csv("out_csv/fomc_realized_decisions.csv")
    realized["fomc_date"] = pd.to_datetime(realized["fomc_date"]).dt.date
    realized = realized.sort_values("fomc_date")
    realized["prev_ffr_upper"] = realized["ffr_upper"].shift(1)
    realized["prev_ffr_upper"] = realized["prev_ffr_upper"].fillna(0.25)
    return realized


def build_event_signal(kalshi: pd.DataFrame, realized: pd.DataFrame, signal_day: int) -> pd.DataFrame:
    rows = []
    for _, r in realized.iterrows():
        fomc = r["fomc_date"]
        k = kalshi[(kalshi["fomc_date"] == fomc) & (kalshi["days_to_fomc"] >= signal_day)].copy()
        if len(k) == 0:
            continue
        k = k.sort_values("days_to_fomc").iloc[0]
        row = k.to_dict()
        row.update(r.to_dict())
        row["signal_day_target"] = signal_day
        row["ffr_pred_change_bps"] = (row.get("mode", np.nan) - row["prev_ffr_upper"]) * 100
        rows.append(row)
    return pd.DataFrame(rows)


def load_asset(symbol: str) -> pd.DataFrame:
    df = pd.read_csv(f"out_csv/{symbol}_yahoo_daily.csv")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.sort_values("date")
    df["asset_ret_next"] = df["adj_close"].shift(-1) / df["adj_close"] - 1
    df["buyhold_ret"] = df["asset_ret_next"]
    return df


def run_event_backtest(event_signals, asset, hold_pre_days, hold_post_days, signal_col, threshold_bps):
    d = asset.copy()
    d["position"] = 0.0
    trades = []

    for _, e in event_signals.iterrows():
        sig = e.get(signal_col, np.nan)
        if pd.isna(sig):
            continue
        pos = 0.0
        if sig <= -threshold_bps:
            pos = 1.0
        elif sig >= threshold_bps:
            pos = -1.0
        if pos == 0:
            continue

        fomc = e["fomc_date"]
        start = (pd.to_datetime(fomc) - pd.Timedelta(days=hold_pre_days)).date()
        end = (pd.to_datetime(fomc) + pd.Timedelta(days=hold_post_days)).date()
        mask = (d["date"] >= start) & (d["date"] <= end)
        d.loc[mask, "position"] = pos
        trades.append({
            "fomc_date": fomc,
            "signal_date": e["trade_date"],
            "signal_col": signal_col,
            "signal": sig,
            "position": pos,
            "start": start,
            "end": end,
            "actual_change_bps": e["change_bps"],
        })

    d["turnover"] = d["position"].diff().abs().fillna(d["position"].abs())
    d["tcost"] = d["turnover"] * TCOST_BPS / 10000.0
    d["strategy_ret"] = d["position"] * d["asset_ret_next"] - d["tcost"]
    d["nav"] = (1 + d["strategy_ret"].fillna(0)).cumprod()
    return d, pd.DataFrame(trades)


def main():
    print("=== 严谨版：真实ETF价格回测 Kalshi FOMC 信号 ===\n")

    kalshi = pd.read_csv("out_csv/kalshi_combined_distributions_daily.csv")
    kalshi["trade_date"] = pd.to_datetime(kalshi["trade_date"]).dt.date
    kalshi["fomc_date"] = pd.to_datetime(kalshi["fomc_date"]).dt.date
    kalshi["days_to_fomc"] = (pd.to_datetime(kalshi["fomc_date"]) - pd.to_datetime(kalshi["trade_date"])).dt.days

    realized = prepare_realized_with_prev()

    all_results = []
    best_records = []

    for symbol in SYMBOLS:
        asset = load_asset(symbol)
        for signal_day in [1, 3, 5, 10, 20]:
            event_sig = build_event_signal(kalshi, realized, signal_day)
            for hold_pre in [1, 3, 5]:
                for sig_col, thr, label in [
                    ("ffr_pred_change_bps", 12.5, "ffr"),
                    ("expected_change_bps", 10.0, "feddec"),
                ]:
                    bt, trades = run_event_backtest(event_sig, asset, hold_pre, 1, sig_col, thr)
                    strategy = f"{symbol}_{label}_T{signal_day}_hold{hold_pre}"
                    stats = perf_stats(bt["strategy_ret"], strategy)
                    stats.update({
                        "symbol": symbol,
                        "signal_type": label,
                        "signal_day": signal_day,
                        "hold_pre": hold_pre,
                        "num_trades": len(trades),
                    })
                    all_results.append(stats)

                    bt.to_csv(f"out_csv/etf_bt_{strategy}.csv", index=False)
                    trades.to_csv(f"out_csv/etf_trades_{strategy}.csv", index=False)

        # buy and hold for symbol
        bh = perf_stats(asset["buyhold_ret"], f"{symbol}_buy_hold")
        bh.update({"symbol": symbol, "signal_type": "buy_hold", "signal_day": np.nan, "hold_pre": np.nan, "num_trades": 1})
        all_results.append(bh)

    res = pd.DataFrame(all_results).sort_values("sharpe", ascending=False)
    res.to_csv("out_csv/kalshi_tradeable_etf_backtest_grid.csv", index=False)

    print("=== 全部标的 Top 20 ===")
    cols = ["strategy", "symbol", "signal_type", "num_trades", "total_return", "ann_return", "ann_vol", "sharpe", "max_drawdown", "win_rate"]
    print(res[cols].head(20).to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n=== 每个标的最优策略 ===")
    best_by_symbol = res[res["signal_type"] != "buy_hold"].sort_values("sharpe", ascending=False).groupby("symbol", as_index=False).first()
    print(best_by_symbol[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    best_by_symbol.to_csv("out_csv/kalshi_tradeable_etf_best_by_symbol.csv", index=False)

    # 画主标的 TLT 最优 vs buyhold
    tlt_best = best_by_symbol[best_by_symbol["symbol"] == "TLT"].iloc[0]
    tlt_strategy = tlt_best["strategy"]
    bt = pd.read_csv(f"out_csv/etf_bt_{tlt_strategy}.csv")
    bt["date"] = pd.to_datetime(bt["date"])
    asset = load_asset("TLT")
    asset["date"] = pd.to_datetime(asset["date"])
    bh_nav = (1 + asset["buyhold_ret"].fillna(0)).cumprod()

    plt.figure(figsize=(12, 7))
    plt.plot(bt["date"], bt["nav"], label=tlt_strategy)
    plt.plot(asset["date"], bh_nav, label="TLT buy_hold", linestyle="--", color="black", alpha=0.7)
    plt.title("Kalshi FOMC Signal Backtest on TLT (Tradeable ETF)")
    plt.xlabel("Date")
    plt.ylabel("NAV")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("out_csv/kalshi_TLT_tradeable_backtest_nav.png", dpi=150, bbox_inches="tight")

    print("\n已保存：")
    print("  out_csv/kalshi_tradeable_etf_backtest_grid.csv")
    print("  out_csv/kalshi_tradeable_etf_best_by_symbol.csv")
    print("  out_csv/kalshi_TLT_tradeable_backtest_nav.png")
    print("  out_csv/etf_bt_*.csv / out_csv/etf_trades_*.csv")


if __name__ == "__main__":
    main()

"""
FOMC 事件窗口版 20Y 国债代理回测

核心：只在 FOMC 会议前后交易，避免每天滚动最近会议带来的噪声。
资产：DGS20 20Y yield 构造的价格代理，ret ~= -duration * Δyield
信号：
- FFR: predicted change = Kalshi mode - 当前实际 FFR upper bound（用上一轮已知 FFR）
- FEDDECISION: expected_change_bps
方向：预期降息 -> 做多20Y；预期加息 -> 做空20Y
"""
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding='utf-8')

DURATION = 17.0
TCOST_BPS = 1.0


def perf_stats(ret: pd.Series, name: str) -> dict:
    ret = ret.dropna()
    nav = (1 + ret).cumprod()
    if len(ret) == 0:
        return {"strategy": name, "n": 0}
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
    # 2022-03-16 前实际 upper 是 0.25
    realized["prev_ffr_upper"] = realized["prev_ffr_upper"].fillna(0.25)
    return realized


def build_event_signal(kalshi, realized, signal_day):
    """取每个 FOMC 的 T-signal_day 最近观测，生成事件级信号。"""
    rows = []
    for _, r in realized.iterrows():
        fomc = r["fomc_date"]
        k = kalshi[(kalshi["fomc_date"] == fomc) & (kalshi["days_to_fomc"] >= signal_day)].copy()
        if len(k) == 0:
            continue
        # 用最接近 signal_day 的那一天；若没有精确 T-N，就取更早最近一天
        k = k.sort_values("days_to_fomc").iloc[0]
        row = k.to_dict()
        row.update(r.to_dict())
        row["signal_day_target"] = signal_day
        row["ffr_pred_change_bps"] = (row.get("mode", np.nan) - row["prev_ffr_upper"]) * 100
        rows.append(row)
    return pd.DataFrame(rows)


def run_event_backtest(event_signals, dgs20, hold_pre_days, hold_post_days, signal_col, threshold_bps, name):
    d = dgs20.copy()
    d["position"] = 0.0

    trades = []
    for _, e in event_signals.iterrows():
        fomc = e["fomc_date"]
        sig = e[signal_col]
        if pd.isna(sig):
            continue
        pos = 0.0
        if sig <= -threshold_bps:
            pos = 1.0
        elif sig >= threshold_bps:
            pos = -1.0
        if pos == 0:
            continue

        start = pd.to_datetime(fomc) - pd.Timedelta(days=hold_pre_days)
        end = pd.to_datetime(fomc) + pd.Timedelta(days=hold_post_days)
        start = start.date()
        end = end.date()
        mask = (d["date"] >= start) & (d["date"] <= end)
        d.loc[mask, "position"] = pos
        trades.append({
            "fomc_date": fomc,
            "signal_date": e["trade_date"],
            "signal": sig,
            "position": pos,
            "start": start,
            "end": end,
            "actual_change_bps": e["change_bps"],
        })

    d["turnover"] = d["position"].diff().abs().fillna(d["position"].abs())
    d["tcost"] = d["turnover"] * TCOST_BPS / 10000.0
    d["strategy_ret"] = d["position"] * d["bond_ret_next"] - d["tcost"]
    d["nav"] = (1 + d["strategy_ret"].fillna(0)).cumprod()
    return d, pd.DataFrame(trades)


def main():
    print("=== FOMC事件窗口 20Y代理回测 ===\n")

    kalshi = pd.read_csv("out_csv/kalshi_combined_distributions_daily.csv")
    kalshi["trade_date"] = pd.to_datetime(kalshi["trade_date"]).dt.date
    kalshi["fomc_date"] = pd.to_datetime(kalshi["fomc_date"]).dt.date
    kalshi["days_to_fomc"] = (pd.to_datetime(kalshi["fomc_date"]) - pd.to_datetime(kalshi["trade_date"])).dt.days

    realized = prepare_realized_with_prev()

    dgs20 = pd.read_csv("out_csv/DGS20_fred_daily.csv")
    dgs20["date"] = pd.to_datetime(dgs20["date"]).dt.date
    dgs20 = dgs20.sort_values("date")
    dgs20["yield_change_next"] = dgs20["dgs20_yield"].shift(-1) - dgs20["dgs20_yield"]
    dgs20["bond_ret_next"] = -DURATION * (dgs20["yield_change_next"] / 100.0)

    configs = []
    for signal_day in [1, 3, 5, 10, 20]:
        event_sig = build_event_signal(kalshi, realized, signal_day)
        event_sig.to_csv(f"out_csv/kalshi_event_signals_T{signal_day}.csv", index=False)
        print(f"T-{signal_day}: 事件信号 {len(event_sig)} 个")

        for hold_pre in [1, 3, 5]:
            for sig_col, thr, label in [
                ("ffr_pred_change_bps", 12.5, "ffr"),
                ("expected_change_bps", 10.0, "feddec"),
            ]:
                bt, trades = run_event_backtest(
                    event_sig, dgs20, hold_pre, 1, sig_col, thr,
                    f"{label}_T{signal_day}_hold{hold_pre}"
                )
                strat_name = f"{label}_T{signal_day}_hold{hold_pre}"
                stats = perf_stats(bt["strategy_ret"], strat_name)
                stats.update({"num_trades": len(trades), "signal_day": signal_day, "hold_pre": hold_pre, "signal_col": sig_col})
                configs.append(stats)
                bt.to_csv(f"out_csv/kalshi_20y_event_bt_{strat_name}.csv", index=False)
                trades.to_csv(f"out_csv/kalshi_20y_event_trades_{strat_name}.csv", index=False)

    res = pd.DataFrame(configs).sort_values("sharpe", ascending=False)
    res.to_csv("out_csv/kalshi_20y_event_backtest_grid.csv", index=False)

    print("\n=== Top 10 配置 ===")
    cols = ["strategy", "num_trades", "total_return", "ann_return", "ann_vol", "sharpe", "max_drawdown", "win_rate"]
    print(res[cols].head(10).to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # 画最佳策略
    best_name = res.iloc[0]["strategy"]
    best_bt = pd.read_csv(f"out_csv/kalshi_20y_event_bt_{best_name}.csv")
    best_bt["date"] = pd.to_datetime(best_bt["date"])

    plt.figure(figsize=(12, 7))
    plt.plot(best_bt["date"], best_bt["nav"], label=best_name)
    buyhold_nav = (1 + best_bt["bond_ret_next"].fillna(0)).cumprod()
    plt.plot(best_bt["date"], buyhold_nav, label="buy_hold_20y_proxy", linestyle="--", color="black", alpha=0.7)
    plt.title("Best FOMC Event Window Strategy on 20Y Treasury Proxy")
    plt.xlabel("Date")
    plt.ylabel("NAV")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("out_csv/kalshi_20y_event_backtest_best_nav.png", dpi=150, bbox_inches="tight")

    print("\n已保存：")
    print("  out_csv/kalshi_20y_event_backtest_grid.csv")
    print("  out_csv/kalshi_20y_event_backtest_best_nav.png")
    print("  out_csv/kalshi_20y_event_bt_*.csv")
    print("  out_csv/kalshi_20y_event_trades_*.csv")


if __name__ == "__main__":
    main()

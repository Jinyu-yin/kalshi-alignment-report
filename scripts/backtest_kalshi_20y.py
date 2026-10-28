"""
Kalshi 信号交易 20年期国债代理回测

资产代理：FRED DGS20 20年期国债收益率
收益近似：20y bond return ~= -duration * Δyield
信号：
1. FEDDECISION expected_change_bps：预期降息 -> 做多长债；预期加息 -> 做空长债
2. FFR mode daily revision：市场预期利率下修 -> 做多长债；上修 -> 做空长债

注意：信号在 trade_date 当天生成，持有下一交易日收益，避免未来函数。
"""
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding='utf-8')

DURATION = 17.0
TCOST_BPS = 1.0


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.cummax()
    dd = nav / peak - 1.0
    return float(dd.min())


def perf_stats(ret: pd.Series, name: str) -> dict:
    ret = ret.dropna()
    if len(ret) == 0:
        return {"strategy": name, "n": 0}
    nav = (1 + ret).cumprod()
    ann_ret = nav.iloc[-1] ** (252 / len(ret)) - 1
    ann_vol = ret.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan
    return {
        "strategy": name,
        "n": len(ret),
        "total_return": nav.iloc[-1] - 1,
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown(nav),
        "win_rate": (ret > 0).mean(),
        "avg_daily_ret": ret.mean(),
    }


def choose_nearest_fomc(kalshi: pd.DataFrame) -> pd.DataFrame:
    """每个交易日只保留最近的未来 FOMC 会议，避免多事件重复计数。"""
    k = kalshi.copy()
    k = k[k["days_to_fomc"] >= 0]
    k = k.sort_values(["trade_date", "days_to_fomc", "fomc_date"])
    return k.groupby("trade_date", as_index=False).first()


def make_positions(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # FEDDECISION 信号：expected_change_bps 越负，越看多长债。
    # 用阈值防止太频繁交易。
    out["pos_feddec_raw"] = 0.0
    out.loc[out["expected_change_bps"] <= -10, "pos_feddec_raw"] = 1.0
    out.loc[out["expected_change_bps"] >= 10, "pos_feddec_raw"] = -1.0

    # 连续版本：把 -expected_change_bps / 50 限制到 [-1,1]
    out["pos_feddec_cont"] = (-out["expected_change_bps"] / 50.0).clip(-1, 1)

    # FFR mode 修正信号：同一最近 FOMC 的 mode 日变化。
    out = out.sort_values("trade_date")
    out["mode_delta"] = out["mode"].diff()
    out["pos_ffr_revision"] = 0.0
    out.loc[out["mode_delta"] <= -0.05, "pos_ffr_revision"] = 1.0
    out.loc[out["mode_delta"] >= 0.05, "pos_ffr_revision"] = -1.0

    # 组合信号：有 FEDDECISION 用 FEDDECISION，否则用 FFR revision
    out["pos_combo"] = out["pos_feddec_cont"].copy()
    out.loc[out["pos_combo"].isna(), "pos_combo"] = out.loc[out["pos_combo"].isna(), "pos_ffr_revision"]

    return out


def apply_backtest(df: pd.DataFrame, pos_col: str) -> pd.DataFrame:
    out = df.copy()
    out["position"] = out[pos_col].fillna(0.0)
    out["turnover"] = out["position"].diff().abs().fillna(out["position"].abs())
    out["tcost"] = out["turnover"] * (TCOST_BPS / 10000.0)
    out["strategy_ret"] = out["position"] * out["bond_ret_next"] - out["tcost"]
    out["nav"] = (1 + out["strategy_ret"].fillna(0)).cumprod()
    return out


def main():
    print("=== Kalshi -> 20Y Treasury Proxy 回测 ===\n")

    kalshi = pd.read_csv("out_csv/kalshi_combined_distributions_daily.csv")
    kalshi["trade_date"] = pd.to_datetime(kalshi["trade_date"]).dt.date
    kalshi["fomc_date"] = pd.to_datetime(kalshi["fomc_date"]).dt.date
    kalshi["days_to_fomc"] = (pd.to_datetime(kalshi["fomc_date"]) - pd.to_datetime(kalshi["trade_date"])).dt.days

    dgs20 = pd.read_csv("out_csv/DGS20_fred_daily.csv")
    dgs20["date"] = pd.to_datetime(dgs20["date"]).dt.date
    dgs20 = dgs20.sort_values("date")
    dgs20["yield_change_next"] = dgs20["dgs20_yield"].shift(-1) - dgs20["dgs20_yield"]
    dgs20["bond_ret_next"] = -DURATION * (dgs20["yield_change_next"] / 100.0)
    dgs20["buyhold_ret"] = dgs20["bond_ret_next"]

    nearest = choose_nearest_fomc(kalshi)
    nearest = make_positions(nearest)

    data = nearest.merge(
        dgs20[["date", "dgs20_yield", "yield_change_next", "bond_ret_next", "buyhold_ret"]],
        left_on="trade_date",
        right_on="date",
        how="inner",
    ).sort_values("trade_date")

    print(f"Kalshi 最近FOMC日频信号: {len(nearest)} 天")
    print(f"与 DGS20 对齐后: {len(data)} 天")
    print(f"时间范围: {data['trade_date'].min()} 到 {data['trade_date'].max()}")
    print(f"平均 days_to_fomc: {data['days_to_fomc'].mean():.1f}\n")

    strategies = {
        "feddec_threshold": "pos_feddec_raw",
        "feddec_continuous": "pos_feddec_cont",
        "ffr_revision": "pos_ffr_revision",
        "combo": "pos_combo",
    }

    results = []
    backtests = {}
    for name, pos_col in strategies.items():
        bt = apply_backtest(data, pos_col)
        backtests[name] = bt
        results.append(perf_stats(bt["strategy_ret"], name))

    # Buy & hold 20Y proxy
    results.append(perf_stats(data["buyhold_ret"], "buy_hold_20y_proxy"))

    res = pd.DataFrame(results)
    res.to_csv("out_csv/kalshi_20y_backtest_summary.csv", index=False)

    print("=== 回测表现 ===")
    display_cols = ["strategy", "n", "total_return", "ann_return", "ann_vol", "sharpe", "max_drawdown", "win_rate"]
    print(res[display_cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # 保存逐日回测结果
    for name, bt in backtests.items():
        bt.to_csv(f"out_csv/kalshi_20y_backtest_{name}.csv", index=False)

    # 画图
    plt.figure(figsize=(13, 8))
    for name, bt in backtests.items():
        plt.plot(pd.to_datetime(bt["trade_date"]), bt["nav"], label=name)
    buyhold_nav = (1 + data["buyhold_ret"].fillna(0)).cumprod()
    plt.plot(pd.to_datetime(data["trade_date"]), buyhold_nav, label="buy_hold_20y_proxy", linestyle="--", color="black", alpha=0.7)
    plt.title("Kalshi Signals on 20Y Treasury Proxy")
    plt.xlabel("Date")
    plt.ylabel("NAV")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("out_csv/kalshi_20y_backtest_nav.png", dpi=150, bbox_inches="tight")

    # 输出最近若干信号检查
    signal_cols = [
        "trade_date", "fomc_date", "days_to_fomc", "mode", "expected_change_bps",
        "pos_feddec_cont", "pos_ffr_revision", "pos_combo", "dgs20_yield", "bond_ret_next"
    ]
    data[signal_cols].tail(30).to_csv("out_csv/kalshi_20y_recent_signals.csv", index=False)

    print("\n已保存：")
    print("  out_csv/kalshi_20y_backtest_summary.csv")
    print("  out_csv/kalshi_20y_backtest_nav.png")
    print("  out_csv/kalshi_20y_recent_signals.csv")
    print("  out_csv/kalshi_20y_backtest_*.csv")

    print("\n注意：当前资产是 DGS20 收益率构造的20年期债券价格代理，不是可交易ETF/期货实盘成交价。")


if __name__ == "__main__":
    main()

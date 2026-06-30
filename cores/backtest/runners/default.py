import typing as t

import numpy as np
import pandas as pd


def run(
    df: pd.DataFrame,
    ctx: t.Dict[str, t.Any],
    params: t.Dict[str, t.Any],
    is_multi: bool,
):
    if df["code"].nunique() != 1:
        raise ValueError("default runner 只支持单code回测")
    df.sort_values(by=["open_time"], inplace=True)

    leverage = params.get("leverage", 1)
    premium = params.get("premium", 0.0005)
    min_margin_ratio = 0.01

    signal_col = params.get("signalName", "signal")
    funding_col = "__funding"
    # 去除连续相同信号
    df_filter = df[signal_col].shift() == df[signal_col]
    df.loc[df_filter, signal_col] = np.nan
    # 模拟资金仓位
    df["__pos"] = df[signal_col].shift().ffill().fillna(0)

    # 是否为交易点
    df["__istrade"] = df["__pos"] != df["__pos"].shift(1).fillna(0)
    # 生成交易序号
    df["__tradeId"] = df.groupby(["__istrade"])["__istrade"].rank(method="first")
    df.loc[~df["__istrade"], "__tradeId"] = None
    df["__tradeId"] = df["__tradeId"].ffill()
    # 下个信号点价格
    df["__priceSell"] = df["close"]
    # 仓位结束时间
    df["__timeSell"] = df["open_time"]
    # 置空非交易点sell价格
    df.loc[~df["__istrade"].shift(-1).fillna(False).astype(np.bool), "__priceSell"] = (
        np.nan
    )
    df.loc[~df["__istrade"], "__timeSell"] = None
    # 同步同交易单的sell价格，最终未平仓视为最后一条close价格平仓
    df["__priceSell"] = df["__priceSell"].bfill().fillna(df["close"].values[-1])
    df["__timeSell"] = df["__timeSell"].bfill()
    df["__timeSell"] = df["__timeSell"].shift(-1)
    # 算出该笔订单的买入价和卖出价格
    df["__priceBuy"] = df["close"].shift(1)
    df.loc[~df["__istrade"], "__priceBuy"] = np.nan
    # 填充同订单内开仓价格，并将第一条数据置零
    df["__priceBuy"] = df["__priceBuy"].ffill().fillna(0)
    # 用最高和最低计算最大盈亏
    df["__lowLine"] = (df["low"] / df["__priceBuy"] - 1) * df["__pos"] * leverage
    df["_highLine"] = (df["high"] / df["__priceBuy"] - 1) * df["__pos"] * leverage
    # 用每个仓位的盈亏量暂时表示资金线
    df[funding_col] = (df["__priceSell"] / df["__priceBuy"] - 1) * df["__istrade"] * df[
        "__pos"
    ] * leverage + 1
    # 将当前仓位盈亏错位到下个仓位起点
    df.loc[~df["__istrade"], funding_col] = np.nan
    df[funding_col] = df[funding_col].ffill().shift(1)
    df.loc[~df["__istrade"], funding_col] = 1
    df[funding_col] = df[funding_col].fillna(1)
    # 根据仓位变化扣除手续费
    df["__trade_volume"] = (df["__pos"] - df["__pos"].shift(1)).fillna(0).abs()
    df["__premium"] = df["__trade_volume"] * float(premium) * leverage
    df[funding_col] *= 1 - df["__premium"]
    # 叠乘出实际仓量
    df[funding_col] = df[funding_col].cumprod()
    df[funding_col] *= (df["close"] / df["__priceBuy"] - 1) * leverage * df["__pos"] + 1
    df[funding_col] = df[funding_col].fillna(1)
    # 计算单次仓位收益率
    df["__income"] = (df["__priceSell"] / df["__priceBuy"] - 1) * df["__pos"] * leverage
    # 检测爆仓，小于爆仓线直接置零
    df.loc[df["__income"] <= -1, "__income"] = -1
    df.loc[
        (df["__lowLine"] < -1) | (df["_highLine"] < -1),
        funding_col,
    ] = 0
    # 最早爆仓的交易ID
    liquidation_idx = df[df[funding_col] <= min_margin_ratio].index
    liquidation_date = None
    if len(liquidation_idx) != 0:
        liquidation_filter = df.index >= liquidation_idx[0]
        liquidation_date = df[liquidation_filter]['open_time'][0]
        df.loc[liquidation_filter, "__istrade"] = False
        df.loc[liquidation_filter, "__pos"] = 0
        df.loc[liquidation_filter, "__income"] = -1
        df.loc[liquidation_filter, funding_col] = 0

    # 计算回撤
    df["__drawdown"] = df[funding_col] / df[funding_col].cummax().bfill() - 1
    df.drop(columns=["__istrade", "__lowLine", "_highLine"], inplace=True)

    # ============ 计算指标 ================

    result = {
        "startTime": ctx['start_time'],
        "endTime": ctx['end_time'],
        "target": ctx['target'],
        "period": ctx['period'],
        "params": params,
        "liquidation": liquidation_date,  # 爆仓
        "data": None
        if is_multi
        else df.to_json(index=False, orient="records"),  # 计算数据
        "maximumDrawdown": -df["__drawdown"].min()
        if df["__drawdown"].min() < 0
        else 0,  # 最大回撤
        "netValue": df[funding_col].values[-1] - df[funding_col].values[0],  # 净值
    }
    # 年化收益率
    result["annualizedRateOfReturn"] = (
        abs(result["netValue"] + 1)
        ** (
            365
            / ((df["open_time"].max() - df["open_time"].min()) // (3600 * 24 * 1000))
        )
        - 1
    )
    # 月化收益率
    result["monthlyRateOfReturn"] = (
        (abs(result["annualizedRateOfReturn"]) + 1) ** (1 / 12) - 1
    ) * (1 if result["annualizedRateOfReturn"] >= 0 else -1)

    # 信号移动到交易时间上，方便统计订单数据
    df[signal_col] = df[signal_col].shift()
    # 分离订单数据
    trade_df = df.loc[
        ~df["__tradeId"].isna(),
        [
            "open_time",
            signal_col,
            "open",
            "close",
            "high",
            "low",
            "__timeSell",
            "__tradeId",
            "__income",
            "__priceSell",
            "__priceBuy",
        ],
    ].copy()
    trade_df = trade_df.groupby("__tradeId", as_index=False).first()
    result["tradeCount"] = len(trade_df)
    # 胜率
    win, lose = sum(trade_df["__income"] > 0), sum(trade_df["__income"] < 0)
    result["winRate"] = 0 if win == 0 else round(win / (win + lose), 2) * 100
    # 最大盈利和亏损
    result["maximumProfit"] = max(trade_df["__income"].max(), 0) * 100
    result["maximumLoss"] = min(trade_df["__income"].min(), 0) * 100
    # 平均盈亏比
    result["averageProfitLossRatio"] = (
        -(
            trade_df[trade_df["__income"] > 0]["__income"].mean()
            / trade_df[trade_df["__income"] < 0]["__income"].mean()
        )
        if (trade_df["__income"] > 0).any() and (trade_df["__income"] < 0).any()
        else None
    )
    # 交易订单数据
    result["tradeData"] = trade_df.to_json(orient="records")

    # NaN 替换为 None，确保 JSON 序列化安全
    def _sanitize(v):
        if isinstance(v, float) and np.isnan(v):
            return None
        if isinstance(v, list):
            return [None if isinstance(x, float) and np.isnan(x) else x for x in v]
        return v

    return {k: _sanitize(v) for k, v in result.items()}

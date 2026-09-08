import typing as t

import numpy as np
import pandas as pd
from utils.types import ContextBase
from utils.types import Runner_Res


def run(
    df: pd.DataFrame,
    ctx: ContextBase,
    params: dict[str, t.Any],
    is_multi: bool,
) -> Runner_Res:
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
    # 生成交易序号：只在「进入非零仓位」时开始新交易；平仓到 0 不产生新交易，归属前一笔
    df["__tradeId"] = (df["__istrade"] & (df["__pos"] != 0)).cumsum()
    df.loc[~df["__istrade"], "__tradeId"] = None
    df["__tradeId"] = df["__tradeId"].ffill()
    # 平仓价：下一交易bar的开盘价（信号在前一根K线收盘生成，次根开盘成交）；最后未平仓用最后close
    df["__priceSell"] = df["open"]
    # 仓位结束时间
    df["__timeSell"] = df["open_time"]
    # 只在交易bar保留open作为平仓价来源，非交易bar置空
    df.loc[~df["__istrade"], "__priceSell"] = np.nan
    df.loc[~df["__istrade"], "__timeSell"] = None
    # 错位到下一交易bar的开盘价，作为本笔交易的平仓价
    df["__priceSell"] = (
        df["__priceSell"].bfill().shift(-1).fillna(float(df["close"].values[-1])) #type: ignore
    )
    df["__timeSell"] = df["__timeSell"].bfill()
    df["__timeSell"] = df["__timeSell"].shift(-1)
    # 开仓价：交易bar的开盘价
    df["__priceBuy"] = df["open"]
    df.loc[~df["__istrade"], "__priceBuy"] = np.nan
    # 填充同订单内开仓价格，并将第一条数据置零
    df["__priceBuy"] = df["__priceBuy"].ffill().fillna(0)
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
    # 计算单次仓位收益率（含杠杆，亏损超过 -100% 即爆仓，封顶为 -1）
    df["__income"] = (df["__priceSell"] / df["__priceBuy"] - 1) * df["__pos"] * leverage
    df.loc[df["__income"] <= -1, "__income"] = -1
    # 最早爆仓的交易ID（单笔 -100% 或盘中估值归零时触发）
    liquidation_idx = df[df[funding_col] <= min_margin_ratio].index
    liquidation_date = None
    if len(liquidation_idx) != 0:
        liquidation_filter = df.index >= liquidation_idx[0]
        liquidation_date = df[liquidation_filter]['open_time'].values[0]
        df.loc[liquidation_filter, "__istrade"] = False
        df.loc[liquidation_filter, "__pos"] = 0
        df.loc[liquidation_filter, "__income"] = -1
        df.loc[liquidation_filter, funding_col] = 0

    # 计算回撤
    df["__drawdown"] = df[funding_col] / df[funding_col].cummax().bfill() - 1
    df.drop(columns=["__istrade"], inplace=True)

    # ============ 计算指标 ================

    result: Runner_Res = {
        "startTime": ctx.get('start_time'),
        "endTime": ctx.get('end_time'),
        "target": ctx['target'],
        "period": ctx['period'],
        "params": params,
        "liquidation": int(liquidation_date) if liquidation_date is not None else None,  # 爆仓
        "premium": (df["__premium"] * df[funding_col]).sum(),  # 手续费
        "data": None
        if (is_multi or len(df) > 1000_000)
        else df.to_json(index=False, orient="records"),  # 计算数据, 多参数时或者大于百万条不返回
        "maximumDrawdown": -df["__drawdown"].min()
        if df["__drawdown"].min() < 0
        else 0,  # 最大回撤
        "netValue": float(df[funding_col].values[-1]),  # 累计净值（期末资金线）# type: ignore
        "annualizedRateOfReturn": 0,
        "monthlyRateOfReturn": 0,
        "tradeData": ""
    }
    # 年化收益率：期末净值^(365/天数)-1；回测不足1天按1天计，避免除零
    days = max(
        (df["open_time"].max() - df["open_time"].min()) // (3600 * 24 * 1000), 1
    )
    result["annualizedRateOfReturn"] = result["netValue"] ** (365 / days) - 1
    # 月化收益率
    result["monthlyRateOfReturn"] = (1 + result["annualizedRateOfReturn"]) ** (1 / 12) - 1

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
    # 扣除每笔交易手续费（开仓+平仓各一次；最后一笔未平仓只扣开仓费），使交易级指标与净收益口径一致
    entry_fee = float(premium) * leverage
    fee_col = np.full(len(trade_df), entry_fee * 2)
    fee_col[trade_df["__timeSell"].isna().to_numpy()] = entry_fee
    trade_df["__income"] = trade_df["__income"] - fee_col
    result["tradeCount"] = len(trade_df)
    # 胜率（含持平单，按全部交易计）
    total = len(trade_df)
    win = int((trade_df["__income"] > 0).sum())
    result["winRate"] = 0 if total == 0 else round(win / total, 2) * 100
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
    return result

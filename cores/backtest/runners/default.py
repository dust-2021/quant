import typing as t

import numpy as np
import pandas as pd


def run(df: pd.DataFrame, ctx: t.Dict[str, t.Any], params: t.Dict[str, t.Any]) -> t.Any:
    df.sort_values(by=['open_time'], inplace=True)

    leverage = params.get('leverage', 1)
    premium = params.get('premium', 0.0005)
    min_margin_ratio = 0.01

    signal_col = 'signal'
    funding_col = '__funding'
    # 去除连续相同信号
    df_filter = df[signal_col].shift() == df[signal_col]
    df.loc[df_filter, signal_col] = np.nan
    # 模拟资金仓位
    df['__pos'] = df[signal_col].shift().fillna(0)

    # 是否为交易点
    df['__istrade'] = df['__pos'] != df['__pos'].shift(1).fillna(0)
    # 生成交易序号
    df['__tradeId'] = df.groupby(['__istrade'])['__istrade'].rank(method='first')
    df.loc[~df['__istrade'], '__tradeId'] = None
    df['__tradeId'].ffill(inplace=True)
    # 下个信号点价格
    df['__priceSell'] = df['close']
    # 仓位结束时间
    df['__timeSell'] = df['open_time']
    df.loc[~df['__istrade'].shift(-1).fillna(False), '__priceSell'] = None
    df.loc[~df['__istrade'], '__timeSell'] = None
    df['__priceSell'].bfill(inplace=True)
    df['__timeSell'].bfill(inplace=True)
    df['__timeSell'] = df['__timeSell'].shift(-1)
    # 算出该笔订单的买入价和卖出价格
    df['__priceBuy'] = df['close'].shift(1)
    df.loc[~df['__istrade'], '__priceBuy'] = np.nan
    df['__priceBuy'].ffill(inplace=True)
    # 用最高和最低计算最大盈亏
    df['__lowLine'] = (df['low'] / df['__priceBuy'] - 1) * df['__pos'] * leverage
    df['_highLine'] = (df['high'] / df['__priceBuy'] - 1) * df['__pos'] * leverage
    # 用每个仓位的盈亏量暂时表示资金线
    df[funding_col] = ((df['__priceSell'] / df['__priceBuy'] - 1) * df['__istrade'] * df['__pos'] * leverage + 1)
    # 将当前仓位盈亏错位到下个仓位起点
    df.loc[~df['__istrade'], funding_col] = np.nan
    df[funding_col] = df[funding_col].ffill().shift(1)
    df.loc[~df['__istrade'], funding_col] = 1
    df[funding_col].fillna(1, inplace=True)
    # 根据仓位变化扣除手续费
    df['_trade_volume'] = (df['__pos'] - df['__pos'].shift(1)).fillna(0).abs()
    df['_premium'] = df['_trade_volume'] * float(premium) * leverage
    df[funding_col] *= 1 - df['_premium']
    # 叠乘出实际仓量
    df[funding_col] = df[funding_col].cumprod()
    df[funding_col] *= ((df['close'] / df['__priceBuy'] - 1) * leverage * df['__pos'] + 1)
    df[funding_col].fillna(1, inplace=True)
    # 计算单次仓位收益率
    df['__income'] = (df['__priceSell'] / df['__priceBuy'] - 1) * df['__pos'] * leverage
    df['__income'] = df['__income'].apply(lambda x: -1 if x <= min_margin_ratio - 1 else x)
    # 检测爆仓，小于爆仓线直接置零
    df.loc[(df['__lowLine'] < min_margin_ratio - 1) | (df['_highLine'] < min_margin_ratio - 1), '_funding'] = 0
    # 最早爆仓的交易ID
    min_id = df[df[funding_col] == 0]['__tradeId'].min()
    min_time = df[df[funding_col] == 0]['open_time'].min()

    if min_id is not None:
        df.loc[df['__tradeId'] > min_id, '__istrade'] = False
        df.loc[df['__tradeId'] > min_id, '__pos'] = 0
        df.loc[df['__tradeId'] >= min_id, '__income'] = -1
        df.loc[df['open_time'] >= min_time, funding_col] = 0

    # df.drop(columns=['__tradeId', '__pos', '__income', '__istrade', '__lowLine', '_highLine'], inplace=True)
    return {
        'liquidation': min_id is not None, 'data': df
    }

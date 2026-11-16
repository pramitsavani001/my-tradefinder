import numpy as np, pandas as pd
import config as C

def atr(df, n=14):
    pc = df.close.shift(1)
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def prep(df):
    df = df.copy(); df["date"] = df.index.date
    d = df.groupby("date").agg(H=("high", "max"), L=("low", "min"))
    d["PDH"], d["PDL"] = d.H.shift(1), d.L.shift(1)
    df = df.join(d[["PDH", "PDL"]], on="date")
    df["ATR"] = atr(df)
    df["VAVG"] = df.volume.rolling(20).mean().shift(1)
    tp = (df.high + df.low + df.close) / 3
    df["VWAP"] = (tp * df.volume).groupby(df.date).cumsum() / df.volume.groupby(df.date).cumsum()
    return df

def signal_at(row, prev_close):
    if np.isnan(row.PDH) or np.isnan(row.ATR) or np.isnan(row.VAVG) or row.VAVG <= 0: return 0
    vol_ok = row.volume >= C.VOL_MULT * row.VAVG
    if row.close > row.PDH and prev_close <= row.PDH and row.close > row.VWAP and vol_ok: return 1
    if row.close < row.PDL and prev_close >= row.PDL and row.close < row.VWAP and vol_ok: return -1
    return 0

def stop_distance(entry, atr_v):
    return max(C.ATR_MULT * atr_v, C.MIN_SL_PCT * entry)

def position_size(capital, risk_pct, risk_per_unit):
    return max(0, int((capital * risk_pct / 100) / risk_per_unit)) if risk_per_unit > 0 else 0

def flow_score(d_ce_oi, d_pe_oi):
    tot = abs(d_ce_oi) + abs(d_pe_oi)
    return 0.0 if tot == 0 else (d_pe_oi - d_ce_oi) / tot

def bias_label(score):
    return "BULLISH" if score > C.BIAS_THRESHOLD else "BEARISH" if score < -C.BIAS_THRESHOLD else "NEUTRAL"

def allowed(signal, market_bias, sector_bias, stock_bias):
    want = "BULLISH" if signal > 0 else "BEARISH"
    opposite = "BEARISH" if signal > 0 else "BULLISH"
    if opposite in (market_bias, sector_bias): return False
    return stock_bias == want

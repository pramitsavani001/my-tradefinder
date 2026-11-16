import time, requests, pyotp
import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from SmartApi import SmartConnect

st.set_page_config(page_title="Pro Trader Terminal (Real-Time)", page_icon="⚡", layout="wide")
st.markdown("<style>.stApp{background-color:#070a12;color:#f8fafc}div[data-testid='stMetric']{background-color:#111827;border:1px solid #1f2937;padding:8px 12px;border-radius:8px}</style>", unsafe_allow_html=True)

# Sidebar Controls
st.sidebar.header("⚡ Live Engine & Risk")
cap = st.sidebar.number_input("Total Capital (₹)", min_value=5000, value=30000, step=5000)
risk_pct = st.sidebar.slider("Max Risk / Trade (%)", 0.5, 5.0, 1.0, 0.5)
rr = st.sidebar.selectbox("Risk : Reward", [1.5, 2.0, 2.5, 3.0], index=1)
tf = st.sidebar.selectbox("Candle Timeframe", ["5m", "15m", "1h"], index=1)
refresh_sec = st.sidebar.selectbox("Live Refresh Speed", [0, 3, 5, 10, 30], index=0, format_func=lambda x: "Manual (OFF)" if x==0 else f"Every {x} Seconds 🔴")

c1, c2 = st.columns([4, 1])
c1.markdown("### ⚡ Institutional Pro Terminal (All NSE F&O Real-Time)")
if c2.button("🔄 Force Sync", use_container_width=True):
    st.cache_data.clear()

@st.cache_data(ttl=86400)
def get_fno_universe():
    fno = {}
    try:
        res = requests.get("https://angelbroking.com", timeout=15).json()
        df_m = pd.DataFrame(res)
        nfo = df_m[(df_m['exch_seg']=='NFO') & (df_m['instrumenttype']=='FUTSTK')]['name'].unique()
        eq = df_m[(df_m['exch_seg']=='NSE') & (df_m['symbol'].str.endswith('-EQ'))]
        for _, r in eq[eq['name'].isin(nfo)].iterrows():
            fno[r['name']] = {"token": str(r['token']), "y_sym": f"{r['name']}.NS"}
    except Exception: pass
    if not fno:
        for s in ["RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","AXISBANK","TATAMOTORS","BAJFINANCE","LT","HAL","BEL","TRENT","ZOMATO","DIXON"]:
            fno[s] = {"token": "", "y_sym": f"{s}.NS"}
    return fno

# Layer 1: Cache Technicals & Historical Charts for 10 mins (Super Fast)
@st.cache_data(ttl=600)
def get_technicals_and_charts(t):
    uni = get_fno_universe()
    tickers = [v["y_sym"] for v in uni.values()]
    intra_list, daily_list = [], []
    for i in range(0, len(tickers), 65):
        chunk = tickers[i:i+65]
        intra_list.append(yf.download(chunk, period="5d", interval=t, group_by='ticker', progress=False, threads=True))
        daily_list.append(yf.download(chunk, period="30d", interval="1d", group_by='ticker', progress=False, threads=True))
    intra, daily = pd.concat(intra_list, axis=1), pd.concat(daily_list, axis=1)
    tech_data, charts = {}, {}
    cols = intra.columns.get_level_values(0) if isinstance(intra.columns, pd.MultiIndex) else []

    for name, info in uni.items():
        try:
            ysym = info["y_sym"]
            if ysym not in cols: continue
            df, ddf = intra[ysym].dropna().copy(), daily[ysym].dropna().copy()
            if len(df) < 22 or len(ddf) < 3: continue
            df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
            df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
            df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
            tp = (df['High'] + df['Low'] + df['Close']) / 3.0
            df['VWAP'] = ((tp * df['Volume']).rolling(14).sum() / df['Volume'].rolling(14).sum()).fillna(df['EMA_20'])
            charts[name] = df
            vol_b = round(float(df['Volume'].iloc[-1]) / float(df['Volume'].tail(20).mean()), 2)
            tech_data[name] = {
                "ema": float(df['EMA_20'].iloc[-1]), "vwap": float(df['VWAP'].iloc[-1]),
                "rsi": float(df['RSI'].iloc[-1]), "atr": float(df['ATR'].iloc[-1]), "vol_b": vol_b,
                "open": float(ddf['Open'].iloc[-1]), "high": float(ddf['High'].iloc[-1]),
                "low": float(ddf['Low'].iloc[-1]), "prev_c": float(ddf['Close'].iloc[-2]), "ltp": float(df['Close'].iloc[-1])
            }
        except Exception: pass
    return tech_data, charts

# Layer 2: Ultra-Fast Angel One Live OHLC Fetcher (Runs every few seconds)
def get_realtime_snapshot(tech_data, c, r_pct, ratio):
    uni = get_fno_universe()
    quotes, status = {}, "Yahoo Feed 🟡"
    ak, cc, mp, ts = st.secrets.get("API_KEY",""), st.secrets.get("CLIENT_CODE",""), st.secrets.get("MPIN",""), st.secrets.get("TOTP_SECRET","")
    if ak and cc and mp and ts:
        try:
            api = SmartConnect(api_key=ak)
            if api.generateSession(cc, mp, pyotp.TOTP(ts).now())['status']:
                status = f"Angel One Live Stream ({len(uni)} F&O) 🟢"
                tokens = [v["token"] for v in uni.values() if v["token"]]
                for i in range(0, len(tokens), 50):
                    q = api.getMarketData("OHLC", {"NSE": tokens[i:i+50]})
                    if q and q.get("status") and "fetched" in q.get("data", {}):
                        for it in q["data"]["fetched"]: quotes[str(it["symbolToken"])] = it
        except Exception: pass

    rows, max_risk = [], (c * r_pct) / 100.0
    for name, td in tech_data.items():
        tok = uni.get(name, {}).get("token", "")
        opn, high, low, prev_c, ltp = td["open"], td["high"], td["low"], td["prev_c"], td["ltp"]
        if tok in quotes:
            qi = quotes[tok]
            if float(qi.get("ltp",0))>0: ltp = float(qi["ltp"])
            if float(qi.get("open",0))>0: opn = float(qi["open"])
            if float(qi.get("high",0))>0: high = float(qi["high"])
            if float(qi.get("low",0))>0: low = float(qi["low"])
            if float(qi.get("close",0))>0: prev_c = float(qi["close"])

        chg = ((ltp - prev_c) / prev_c) * 100 if prev_c > 0 else 0
        sl_pts = 1.5 * td["atr"]
        qty = int(max_risk / sl_pts) if sl_pts > 0 else 0

        if ltp > td["ema"] and ltp > td["vwap"] and td["rsi"] >= 52 and chg > 0.3:
            sig, sl, tgt = "🟢 BUY", round(ltp - sl_pts, 2), round(ltp + (sl_pts * ratio), 2)
        elif ltp < td["ema"] and ltp < td["vwap"] and td["rsi"] <= 48 and chg < -0.3:
            sig, sl, tgt = "🔴 SELL", round(ltp + sl_pts, 2), round(ltp - (sl_pts * ratio), 2)
        else:
            sig, sl, tgt, qty = "⚪ WAIT", "-", "-", "-"

        rows.append({
            "Stock": name, "LTP (₹)": round(ltp, 2), "Change (%)": round(chg, 2),
            "Open": round(opn, 2), "High": round(high, 2), "Low": round(low, 2), "Prev Close": round(prev_c, 2),
            "Signal": sig, "Safe Qty": qty if qty != 0 else "-", "Stop-Loss": sl, "Target": tgt,
            "Vol Boost": td["vol_b"], "RSI": round(td["rsi"], 1), "VWAP": round(td["vwap"], 2)
        })
    return pd.DataFrame(rows), status

with st.spinner("Initializing Live Market Engine..."):
    tech_data, charts = get_technicals_and_charts(tf)
    df, status = get_realtime_snapshot(tech_data, cap, risk_pct, rr)

st.caption(f"Feed: **{status}** | Scanned: **{len(df)} F&O Stocks** | Max Risk: **₹{int(cap * risk_pct / 100):,}**")

view = st.radio("View", ["📊 Top 20 Gainers & Losers (OHLC + Signals)", "🖥️ 3-Column Pro Trader Terminal", "💥 Volume & Breakout Screener"], horizontal=True, label_visibility="collapsed")

if not df.empty:
    if view == "📊 Top 20 Gainers & Losers (OHLC + Signals)":
        st.subheader("🚀 Top 20 F&O Gainers (Real-Time OHLC + Buy/Sell Signals)")
        g20 = df.sort_values("Change (%)", ascending=False).head(20)
        st.dataframe(g20[["Stock", "LTP (₹)", "Change (%)", "Open", "High", "Low", "Prev Close", "Signal", "Safe Qty", "Stop-Loss", "Target"]], use_container_width=True, hide_index=True, height=550)

        st.divider()
        st.subheader("📉 Top 20 F&O Losers (Real-Time OHLC + Buy/Sell Signals)")
        l20 = df.sort_values("Change (%)", ascending=True).head(20)
        st.dataframe(l20[["Stock", "LTP (₹)", "Change (%)", "Open", "High", "Low", "Prev Close", "Signal", "Safe Qty", "Stop-Loss", "Target"]], use_container_width=True, hide_index=True, height=550)

    elif view == "🖥️ 3-Column Pro Trader Terminal":
        col_left, col_mid, col_right = st.columns([2.2, 5.5, 2.3])
        with col_left:
            st.markdown("#### 📋 Live Watchlist")
            sel = st.selectbox("Select Stock:", sorted(df["Stock"].tolist()), label_visibility="collapsed")
            top_movers = pd.concat([df.sort_values("Change (%)", ascending=False).head(10), df.sort_values("Change (%)", ascending=True).head(10)])
            st.dataframe(top_movers[["Stock", "LTP (₹)", "Change (%)"]], use_container_width=True, hide_index=True, height=480)

        ri = df[df["Stock"] == sel].iloc
        with col_mid:
            st.markdown(f"#### 🕯️ {sel} Live Chart (20 EMA + VWAP + RSI)")
            st.link_button(f"↗️ Open {sel} Superchart on TradingView", f"https://tradingview.com{sel.replace('&','_').replace('-','_')}/", use_container_width=True)
            if sel in charts:
                cdf = charts[sel].tail(75)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.72, 0.28])
                fig.add_trace(go.Candlestick(x=cdf.index, open=cdf['Open'], high=cdf['High'], low=cdf['Low'], close=cdf['Close'], name="Price"), row=1, col=1)
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['EMA_20'], mode='lines', line=dict(color='#f59e0b', width=2), name="20 EMA"), row=1, col=1)
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['VWAP'], mode='lines', line=dict(color='#a855f7', width=2, dash='dot'), name="VWAP"), row=1, col=1)
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['RSI'], mode='lines', line=dict(color='#38bdf8', width=1.8), name="RSI"), row=2, col=1)

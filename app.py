import time, requests, pyotp
import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from SmartApi import SmartConnect

st.set_page_config(page_title="TradeFinder Pro (All F&O)", page_icon="⚡", layout="wide")
st.markdown("<style>.stApp{background-color:#0b0f19;color:#f8fafc}div[data-testid='stMetric']{background-color:#131a2a;border:1px solid #1e293b;padding:10px;border-radius:8px}</style>", unsafe_allow_html=True)

st.sidebar.header("💰 Risk & Capital Manager")
cap = st.sidebar.number_input("Total Capital (₹)", min_value=5000, value=30000, step=5000)
risk_pct = st.sidebar.slider("Max Risk Per Trade (%)", 0.5, 5.0, 1.0, 0.5)
rr = st.sidebar.selectbox("Risk : Reward", [1.5, 2.0, 2.5, 3.0], index=1)
tf = st.sidebar.selectbox("Timeframe", ["5m", "15m", "1h"], index=1)
auto_live = st.sidebar.toggle("🔴 Auto-Live Mode (30s)", value=False)

c1, c2 = st.columns([4, 1])
c1.markdown("### 💠 TradeFinder Pro Live (All Option Chain / F&O Stocks)")
if c2.button("🔄 Sync All F&O", use_container_width=True):
    st.cache_data.clear()

SECTOR_MAP = {
    "HDFCBANK":"Banking","ICICIBANK":"Banking","SBIN":"Banking","AXISBANK":"Banking","KOTAKBANK":"Banking","INDUSINDBK":"Banking","BANKBARODA":"Banking","PNB":"Banking","CANBK":"Banking","FEDERALBNK":"Banking","IDFCFIRSTB":"Banking","AUBANK":"Banking",
    "BAJFINANCE":"Finance","BAJAJFINSV":"Finance","CHOLAFIN":"Finance","SHRIRAMFIN":"Finance","PFC":"Finance","RECLTD":"Finance","SBILIFE":"Finance","HDFCLIFE":"Finance","JIOFIN":"Finance","MUTHOOTFIN":"Finance","ABCAPITAL":"Finance",
    "TCS":"IT","INFY":"IT","WIPRO":"IT","HCLTECH":"IT","TECHM":"IT","LTIM":"IT","PERSISTENT":"IT","COFORGE":"IT","MPHASIS":"IT","KPITTECH":"IT","TATAELXSI":"IT",
    "RELIANCE":"Energy","ONGC":"Energy","NTPC":"Energy","POWERGRID":"Energy","COALINDIA":"Energy","TATAPOWER":"Energy","ADANIGREEN":"Energy","BPCL":"Energy","IOC":"Energy","GAIL":"Energy","NHPC":"Energy",
    "TATAMOTORS":"Auto","MARUTI":"Auto","M&M":"Auto","BAJAJ-AUTO":"Auto","EICHERMOT":"Auto","TVSMOTOR":"Auto","ASHOKLEY":"Auto","HEROMOTOCO":"Auto","BHARATFORG":"Auto","MOTHERSON":"Auto",
    "SUNPHARMA":"Pharma","CIPLA":"Pharma","DRREDDY":"Pharma","DIVISLAB":"Pharma","APOLLOHOSP":"Pharma","LUPIN":"Pharma","AUROPHARMA":"Pharma","TORNTPHARM":"Pharma","ZYDUSLIFE":"Pharma","MAXHEALTH":"Pharma",
    "TATASTEEL":"Metal","HINDALCO":"Metal","JSWSTEEL":"Metal","VEDL":"Metal","JINDALSTEL":"Metal","NMDC":"Metal","SAIL":"Metal","NATIONALUM":"Metal","HINDCOPPER":"Metal",
    "ITC":"FMCG","HINDUNILVR":"FMCG","NESTLEIND":"FMCG","BRITANNIA":"FMCG","TATACONSUM":"FMCG","VBL":"FMCG","GODREJCP":"FMCG","DABUR":"FMCG","MARICO":"FMCG",
    "LT":"Infra & Defence","ADANIENT":"Infra & Defence","ADANIPORTS":"Infra & Defence","HAL":"Infra & Defence","BEL":"Infra & Defence","BHEL":"Infra & Defence","MAZDOCK":"Infra & Defence","SIEMENS":"Infra & Defence","ABB":"Infra & Defence",
    "DLF":"Realty","GODREJPROP":"Realty","OBEROIRLTY":"Realty","LODHA":"Realty","TITAN":"Consumer","TRENT":"Consumer","ZOMATO":"Consumer","ETERNAL":"Consumer","DIXON":"Consumer","INDIGO":"Consumer","IRCTC":"Consumer","BHARTIARTL":"Telecom"
}

@st.cache_data(ttl=86400)
def get_fno_universe():
    fno = {}
    try:
        res = requests.get("https://angelbroking.com", timeout=15).json()
        df_m = pd.DataFrame(res)
        nfo = df_m[(df_m['exch_seg']=='NFO') & (df_m['instrumenttype']=='FUTSTK')]['name'].unique()
        eq = df_m[(df_m['exch_seg']=='NSE') & (df_m['symbol'].str.endswith('-EQ'))]
        for _, r in eq[eq['name'].isin(nfo)].iterrows():
            s = r['name']
            fno[s] = {"token": str(r['token']), "y_sym": f"{s}.NS", "sector": SECTOR_MAP.get(s, "Midcap F&O")}
    except Exception:
        pass
    if not fno:
        for s, sec in SECTOR_MAP.items():
            fno[s] = {"token": "", "y_sym": f"{s}.NS", "sector": sec}
    return fno

@st.cache_data(ttl=60)
def get_indices():
    res = {}
    for n, s in {"NIFTY 50":"^NSEI","BANK NIFTY":"^NSEBANK","INDIA VIX":"^INDIAVIX","DAX":"^GDAXI","DOW":"^DJI","BTC":"BTC-USD"}.items():
        try:
            d = yf.download(s, period="2d", interval="1d", progress=False)
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
            p, c = float(d['Close'].iloc[-2]), float(d['Close'].iloc[-1])
            res[n] = (round(c, 2), round(((c - p) / p) * 100, 2))
        except Exception: pass
    return res

@st.cache_data(ttl=30)
def scan_market(t, c, r_pct, ratio):
    uni = get_fno_universe()
    results, charts, quotes = [], {}, {}
    status = "Yahoo Delay Feed 🟡"
    ak, cc, mp, ts = st.secrets.get("API_KEY",""), st.secrets.get("CLIENT_CODE",""), st.secrets.get("MPIN",""), st.secrets.get("TOTP_SECRET","")
    if ak and cc and mp and ts:
        try:
            api = SmartConnect(api_key=ak)
            if api.generateSession(cc, mp, pyotp.TOTP(ts).now())['status']:
                status = f"Angel One 0-Sec Live ({len(uni)} F&O) 🟢"
                tokens = [v["token"] for v in uni.values() if v["token"]]
                for i in range(0, len(tokens), 50):
                    q = api.getMarketData("OHLC", {"NSE": tokens[i:i+50]})
                    if q and q.get("status") and "fetched" in q.get("data", {}):
                        for it in q["data"]["fetched"]: quotes[str(it["symbolToken"])] = it
        except Exception: pass

    tickers = [v["y_sym"] for v in uni.values()]
    intra = yf.download(tickers, period="5d", interval=t, group_by='ticker', progress=False, threads=True)
    daily = yf.download(tickers, period="55d", interval="1d", group_by='ticker', progress=False, threads=True)
    max_risk = (c * r_pct) / 100.0
    cols = intra.columns.get_level_values(0) if isinstance(intra.columns, pd.MultiIndex) else []

    for name, info in uni.items():
        try:
            ysym = info["y_sym"]
            if ysym not in cols: continue
            df, ddf = intra[ysym].dropna().copy(), daily[ysym].dropna().copy()
            if len(df) < 22 or len(ddf) < 5: continue
            df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
            df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
            df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
            tp = (df['High'] + df['Low'] + df['Close']) / 3.0
            df['VWAP'] = ((tp * df['Volume']).rolling(14).sum() / df['Volume'].rolling(14).sum()).fillna(df['EMA_20'])
            charts[name] = df

            prev_c, curr_p, d_high, d_low = float(ddf['Close'].iloc[-2]), float(df['Close'].iloc[-1]), float(ddf['High'].iloc[-1]), float(ddf['Low'].iloc[-1])
            if info["token"] in quotes:
                qi = quotes[info["token"]]
                if float(qi.get("ltp",0))>0: curr_p = float(qi["ltp"])
                if float(qi.get("high",0))>0: d_high = float(qi["high"])
                if float(qi.get("low",0))>0: d_low = float(qi["low"])
                if float(qi.get("close",0))>0: prev_c = float(qi["close"])

            chg = ((curr_p - prev_c) / prev_c) * 100
            vol_b = round(float(df['Volume'].iloc[-1]) / float(df['Volume'].tail(20).mean()), 2)
            ema_v, vwap_v, rsi_v, atr_v = float(df['EMA_20'].iloc[-1]), float(df['VWAP'].iloc[-1]), float(df['RSI'].iloc[-1]), float(df['ATR'].iloc[-1])
            sl_pts = 1.5 * atr_v
            qty = int(max_risk / sl_pts) if sl_pts > 0 else 0

            if curr_p > ema_v and curr_p > vwap_v and rsi_v >= 52 and chg > 0.3:
                sig, sl, tgt = "🟢 BUY", round(curr_p - sl_pts, 2), round(curr_p + (sl_pts * ratio), 2)
            elif curr_p < ema_v and curr_p < vwap_v and rsi_v <= 48 and chg < -0.3:
                sig, sl, tgt = "🔴 SELL", round(curr_p + sl_pts, 2), round(curr_p - (sl_pts * ratio), 2)
            else:
                sig, sl, tgt, qty = "⚪ WAIT", "-", "-", "-"

            tv_s = name.replace("&", "_").replace("-", "_")
            results.append({
                "Stock": name, "Sector": info["sector"], "TV_Link": f"https://tradingview.com{tv_s}/",
                "LTP (₹)": round(curr_p, 2), "Day Low": round(d_low, 2), "Day High": round(d_high, 2),
                "Change (%)": round(chg, 2), "VWAP": round(vwap_v, 2), "VWAP Trend": "Above 🟢" if curr_p > vwap_v else "Below 🔴",
                "Vol Boost (x)": vol_b, "RSI": round(rsi_v, 1), "Signal": sig, "Safe Qty": qty if qty != 0 else "-",
                "Stop-Loss": sl, "Target": tgt,
                "Dist_High_%": round(((d_high - curr_p) / d_high) * 100, 2), "Dist_Low_%": round(((curr_p - d_low) / d_low) * 100, 2),
                "BO_10D": curr_p >= float(ddf['High'].iloc[-11:-1].max()) * 0.995, "BO_50D": curr_p >= float(ddf['High'].iloc[-51:-1].max()) * 0.995
            })
        except Exception: pass
    return pd.DataFrame(results), charts, status

idx = get_indices()
if idx:
    cols = st.columns(len(idx))
    for i, (k, (v, ch)) in enumerate(idx.items()): cols[i].metric(k, f"{v:,}", f"{ch}%")

with st.spinner("Scanning All ~200+ NSE F&O Stocks..."):
    df, charts, status = scan_market(tf, cap, risk_pct, rr)

st.caption(f"Feed: **{status}** | Scanned: **{len(df)} F&O Stocks** | Max Risk: **₹{int(cap * risk_pct / 100):,}**")
nav = st.radio("Nav", ["⚡ Market Pulse", "🔥 Heatmap & RSI", "📊 Sector Scope", "📈 Swing Breakout", "🕯️ Live Chart"], horizontal=True, label_visibility="collapsed")
cfg = {"TV_Link": st.column_config.LinkColumn("Chart", display_text="TradingView ↗️")}

if not df.empty:
    if nav == "⚡ Market Pulse":
        a, b = st.columns(2)
        a.subheader("🚀 Top 10 Gainers")

import time, requests, pyotp
import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from SmartApi import SmartConnect

st.set_page_config(page_title="TradeFinder Pro Workspace", page_icon="💠", layout="wide")
st.markdown("<style>.stApp{background-color:#f4f7fe;color:#1e293b}div[data-testid='stMetric']{background-color:#ffffff;border:1px solid #e2e8f0;padding:12px;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,0.04)}section[data-testid='stSidebar']{background-color:#ffffff;border-right:1px solid #e2e8f0}</style>", unsafe_allow_html=True)

st.sidebar.markdown("## 💠 TradeFinder Pro")
page = st.sidebar.radio("MENU", ["🏠 Home", "⚡ Market Pulse", "🔥 Insider Strategy", "🕯️ Live Chart & Risk"])
st.sidebar.divider()
cap = st.sidebar.number_input("Total Capital (₹)", 5000, 5000000, 30000, 5000)
risk_pct = st.sidebar.slider("Risk / Trade (%)", 0.5, 5.0, 1.0, 0.5)
rr = st.sidebar.selectbox("Risk : Reward", [1.5, 2.0, 2.5, 3.0], index=1)
tf = st.sidebar.selectbox("Timeframe", ["5m", "15m", "1h"], index=1)
ref_sec = st.sidebar.selectbox("Auto-Refresh", [0, 5, 10, 30], format_func=lambda x: "OFF" if x==0 else f"Every {x}s 🔴")

ALL_FNO = ["RELIANCE","TCS","HDFCBANK","ICICIBANK","BHARTIARTL","SBIN","INFY","LICI","ITC","HINDUNILVR","LT","BAJFINANCE","HCLTECH","MARUTI","SUNPHARMA","ADANIENT","KOTAKBANK","TITAN","ONGC","TATAMOTORS","NTPC","AXISBANK","ADANIPORTS","ULTRACEMCO","COALINDIA","BAJAJFINSV","BAJAJ-AUTO","HAL","BEL","TRENT","ZOMATO","M&M","POWERGRID","TATASTEEL","JSWSTEEL","SIEMENS","WIPRO","NESTLEIND","IOC","DLF","VBL","JIOFIN","GRASIM","TECHM","HINDALCO","PIDILITIND","LTIM","SBILIFE","HDFCLIFE","INDIGO","BPCL","DIVISLAB","CIPLA","BRITANNIA","EICHERMOT","GODREJCP","TVSMOTOR","GAIL","ABB","CHOLAFIN","BANKBARODA","SHRIRAMFIN","VEDL","PNB","HAVELLS","TATAPOWER","DRREDDY","DABUR","AMBUJACEM","INDUSINDBK","HEROMOTOCO","APOLLOHOSP","TORNTPHARM","ICICIGI","UNIONBANK","CANBK","ZYDUSLIFE","CGPOWER","BHEL","JINDALSTEL","DIXON","MAXHEALTH","PERSISTENT","POLYCAB","CUMMINSIND","NAUKRI","MARICO","MUTHOOTFIN","SRF","COLPAL","LUPIN","AUROPHARMA","IDFCFIRSTB","INDUSTOWER","OBEROIRLTY","FEDERALBNK","ASHOKLEY","TATAELXSI","COFORGE","MPHASIS","PIIND","ASTRAL","HINDPETRO","IRCTC","PETRONET","ALKEM","UPL","CONCOR","VOLTAS","PAGEIND","SAIL","NMDC","BHARATFORG","MOTHERSON","BALKRISIND","MRF","EXIDEIND","BOSCHLTD","BIOCON","GLENMARK","LAURUSLABS","FORTIS","NATIONALUM","HINDCOPPER","UBL","MAZDOCK","GODREJPROP","LODHA","PRESTIGE","INDHOTEL","PAYTM","SHREECEM","ACC","DALBHARAT","DEEPAKNTR","AARTIIND","KPITTECH","LTTS","OFSS","NHPC","SJVN","CESC","IGL","AUBANK","BANDHANBNK","INDIANB","PFC","RECLTD","ABCAPITAL","LTF","MANAPPURAM","LICHSGFIN","IDEA","TATACONSUM","APOLLOTYRE"]

@st.cache_data(ttl=86400)
def get_tokens():
    tmap = {}
    try:
        for r in requests.get("https://angelbroking.com", timeout=25).json():
            if r.get("exch_seg") == "NSE" and str(r.get("symbol", "")).endswith("-EQ"): tmap[r["name"]] = str(r["token"])
    except Exception: pass
    return tmap

@st.cache_data(ttl=600)
def load_base_data(t):
    tickers = [f"{s}.NS" for s in ALL_FNO]
    intra_l, daily_l = [], []
    for i in range(0, len(tickers), 55):
        ch = tickers[i:i+55]
        intra_l.append(yf.download(ch, period="5d", interval=t, group_by='ticker', progress=False, threads=True))
        daily_l.append(yf.download(ch, period="10d", interval="1d", group_by='ticker', progress=False, threads=True))
    intra, daily = pd.concat(intra_l, axis=1), pd.concat(daily_l, axis=1)
    tech, charts = {}, {}
    cols = intra.columns.get_level_values(0) if isinstance(intra.columns, pd.MultiIndex) else []
    for name in ALL_FNO:
        try:
            ysym = f"{name}.NS"
            if ysym not in cols: continue
            df, ddf = intra[ysym].dropna().copy(), daily[ysym].dropna().copy()
            if len(df) < 20 or len(ddf) < 2: continue
            df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
            df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
            df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
            tp = (df['High'] + df['Low'] + df['Close']) / 3.0
            df['VWAP'] = ((tp * df['Volume']).rolling(14).sum() / df['Volume'].rolling(14).sum()).fillna(df['EMA_20'])
            charts[name] = df
            avg_v = float(df['Volume'].tail(20).mean())
            cur_v = float(df['Volume'].iloc[-1])
            vol_b = round(cur_v / avg_v, 2) if avg_v > 0 else 1.0
            spike_5m = ((float(df['Close'].iloc[-1]) - float(df['Open'].iloc[-1])) / float(df['Open'].iloc[-1])) * 100
            tech[name] = {"ema":float(df['EMA_20'].iloc[-1]),"vwap":float(df['VWAP'].iloc[-1]),"rsi":float(df['RSI'].iloc[-1]),"atr":float(df['ATR'].iloc[-1]),"vol_b":vol_b,"spike":round(spike_5m,2),"open":float(ddf['Open'].iloc[-1]),"high":float(ddf['High'].iloc[-1]),"low":float(ddf['Low'].iloc[-1]),"prev_c":float(ddf['Close'].iloc[-2]),"ltp":float(df['Close'].iloc[-1])}
        except Exception: pass
    return tech, charts

def get_live_df(tech, c, r_pct, ratio):
    tmap = get_tokens()
    quotes, status = {}, "Yahoo Feed 🟡"
    ak, cc, mp, ts = st.secrets.get("API_KEY",""), st.secrets.get("CLIENT_CODE",""), st.secrets.get("MPIN",""), st.secrets.get("TOTP_SECRET","")
    if ak and cc and mp and ts and tmap:
        try:
            api = SmartConnect(api_key=ak)
            if api.generateSession(cc, mp, pyotp.TOTP(ts).now())['status']:
                tokens = [tmap[s] for s in tech.keys() if s in tmap]
                for i in range(0, len(tokens), 50):
                    q = api.getMarketData("OHLC", {"NSE": tokens[i:i+50]})
                    if q and q.get("status") and "fetched" in q.get("data", {}):
                        for it in q["data"]["fetched"]: quotes[str(it["symbolToken"])] = it
                status = f"Angel One Live ({len(quotes)} F&O) 🟢"
        except Exception: pass
    rows, max_risk = [], (c * r_pct) / 100.0
    for name, td in tech.items():
        tok = tmap.get(name, "")
        opn, high, low, prev_c, ltp = td["open"], td["high"], td["low"], td["prev_c"], td["ltp"]
        if tok in quotes:
            qi = quotes[tok]
            if float(qi.get("ltp",0))>0: ltp = float(qi["ltp"])
            if float(qi.get("open",0))>0: opn = float(qi["open"])
            if float(qi.get("high",0))>0: high = float(qi["high"])
            if float(qi.get("low",0))>0: low = float(qi["low"])
            if float(qi.get("close",0))>0: prev_c = float(qi["close"])
        chg = ((ltp - prev_c) / prev_c) * 100 if prev_c > 0 else 0
        sl_pts = max(1.5 * td["atr"], ltp * 0.004)
        qty = max(1, int(max_risk / sl_pts))
        if ltp > td["ema"] and chg > 0.2: sig, sl, tgt = "🟢 BUY", round(ltp - sl_pts, 2), round(ltp + (sl_pts * ratio), 2)
        elif ltp < td["ema"] and chg < -0.2: sig, sl, tgt = "🔴 SELL", round(ltp + sl_pts, 2), round(ltp - (sl_pts * ratio), 2)
        else: sig, sl, tgt, qty = "⚪ WAIT", "-", "-", "-"
        rows.append({"Stock":name,"LTP":round(ltp,2),"Chg %":round(chg,2),"Open":round(opn,2),"High":round(high,2),"Low":round(low,2),"Signal":sig,"Qty":qty,"SL":sl,"Target":tgt,"Boost (x)":td["vol_b"],"Spike %":td["spike"],"RSI":round(td["rsi"],1),"VWAP":round(td["vwap"],2),"Dist_H":round(((high-ltp)/high)*100,2),"Dist_L":round(((ltp-low)/low)*100,2)})
    return pd.DataFrame(rows), status

tech_data, charts = load_base_data(tf)
df, status = get_live_df(tech_data, cap, risk_pct, rr)

# Top Global Indices Strip (Like Image 2)
c_head, c_btn = st.columns([4, 1])
c_head.markdown(f"### Welcome, pramit | `{status}`")
if c_btn.button("🔄 Sync Live", use_container_width=True): st.cache_data.clear()

if not df.empty:
    sel_stock = st.selectbox("🔍 Quick Chart Launcher (Select Any F&O Stock):", sorted(df["Stock"].tolist()))
    tv_clean = sel_stock.replace("&", "_").replace("-", "_")
    st.link_button(f"↗️ Open {sel_stock} Live Chart on TradingView", f"https://tradingview.com:{tv_clean}")

    if page == "🏠 Home":
        st.info("👈 Select **⚡ Market Pulse**, **🔥 Insider Strategy**, or **🕯️ Live Chart & Risk** from the left menu (All Pro Tools Unlocked 🔓).")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total F&O Scanned", len(df))
        m2.metric("Bullish (BUY) Setups", len(df[df["Signal"] == "🟢 BUY"]))
        m3.metric("Bearish (SELL) Setups", len(df[df["Signal"] == "🔴 SELL"]))
        m4.metric("Max Risk / Trade", f"₹{int(cap * risk_pct / 100)}")

    elif page == "⚡ Market Pulse":
        st.markdown("### ⚡ Market Pulse (Live Institutional Scanners)")
        c1, c2 = st.columns(2)
        c1.subheader("🚀 Top 20 Gainers")
        c1.dataframe(df.sort_values("Chg %", ascending=False).head(20)[["Stock","LTP","Chg %","Open","High","Low","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)
        c2.subheader("📉 Top 20 Losers")
        c2.dataframe(df.sort_values("Chg %", ascending=True).head(20)[["Stock","LTP","Chg %","Open","High","Low","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)

        st.divider()
        b1, b2 = st.columns(2)
        b1.subheader("💥 Intraday Boost (Volume Spike)")
        b1.dataframe(df.sort_values("Boost (x)", ascending=False).head(15)[["Stock","LTP","Chg %","Boost (x)","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)
        b2.subheader("🎯 Breakout Beacon (High Momentum)")
        bo = df[df["Signal"] != "⚪ WAIT"].sort_values("Boost (x)", ascending=False).head(15)
        b2.dataframe(bo[["Stock","LTP","Chg %","RSI","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)

        st.divider()
        l1, l2 = st.columns(2)
        l1.subheader("🏔️ Top Level Stocks (Near Day High)")

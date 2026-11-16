import time, requests, pyotp
import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from SmartApi import SmartConnect

st.set_page_config(page_title="Pro Trader Terminal (All F&O)", page_icon="⚡", layout="wide")
st.markdown("<style>.stApp{background-color:#070a12;color:#f8fafc}div[data-testid='stMetric']{background-color:#111827;border:1px solid #1f2937;padding:8px 12px;border-radius:8px}</style>", unsafe_allow_html=True)

st.sidebar.header("⚡ Live Engine & Risk")
cap = st.sidebar.number_input("Total Capital (₹)", min_value=5000, value=30000, step=5000)
risk_pct = st.sidebar.slider("Max Risk / Trade (%)", 0.5, 5.0, 1.0, 0.5)
rr = st.sidebar.selectbox("Risk : Reward", [1.5, 2.0, 2.5, 3.0], index=1)
tf = st.sidebar.selectbox("Candle Timeframe", ["5m", "15m", "1h"], index=1)
refresh_sec = st.sidebar.selectbox("Live Refresh Speed", [0, 5, 10, 30], index=0, format_func=lambda x: "Manual (OFF)" if x==0 else f"Every {x} Seconds 🔴")

c1, c2 = st.columns([4, 1])
c1.markdown("### ⚡ Institutional Pro Terminal (All NSE F&O Real-Time)")
if c2.button("🔄 Force Sync", use_container_width=True):
    st.cache_data.clear()

ALL_FNO_STOCKS = [
    "RELIANCE","TCS","HDFCBANK","ICICIBANK","BHARTIARTL","SBIN","INFY","LICI","ITC","HINDUNILVR",
    "LT","BAJFINANCE","HCLTECH","MARUTI","SUNPHARMA","ADANIENT","KOTAKBANK","TITAN","ONGC","TATAMOTORS",
    "NTPC","AXISBANK","ADANIPORTS","ULTRACEMCO","COALINDIA","BAJAJFINSV","BAJAJ-AUTO","HAL","BEL","TRENT",
    "ZOMATO","M&M","POWERGRID","TATASTEEL","JSWSTEEL","SIEMENS","WIPRO","NESTLEIND","IOC","DLF",
    "VBL","JIOFIN","GRASIM","TECHM","HINDALCO","PIDILITIND","LTIM","SBILIFE","HDFCLIFE","INDIGO",
    "BPCL","DIVISLAB","CIPLA","BRITANNIA","EICHERMOT","GODREJCP","TVSMOTOR","GAIL","ABB","CHOLAFIN",
    "BANKBARODA","SHRIRAMFIN","VEDL","PNB","HAVELLS","TATAPOWER","DRREDDY","DABUR","AMBUJACEM","INDUSINDBK",
    "HEROMOTOCO","APOLLOHOSP","MANKIND","TORNTPHARM","ICICIGI","UNIONBANK","CANBK","ZYDUSLIFE","CGPOWER","BHEL",
    "JINDALSTEL","DIXON","MAXHEALTH","PERSISTENT","POLYCAB","CUMMINSIND","SUZLON","NAUKRI","MARICO","MUTHOOTFIN",
    "SRF","COLPAL","LUPIN","AUROPHARMA","IDFCFIRSTB","INDUSTOWER","OBEROIRLTY","FEDERALBNK","ASHOKLEY","TATAELXSI",
    "COFORGE","MPHASIS","PIIND","ASTRAL","HINDPETRO","IRCTC","PETRONET","ALKEM","UPL","CONCOR",
    "VOLTAS","PAGEIND","SAIL","NMDC","BHARATFORG","MOTHERSON","BALKRISIND","MRF","EXIDEIND","BOSCHLTD",
    "BIOCON","GLENMARK","LAURUSLABS","FORTIS","NATIONALUM","HINDCOPPER","UBL","MAZDOCK","GMRAIRPORT","GODREJPROP",
    "LODHA","PRESTIGE","BLUESTARCO","INDHOTEL","PAYTM","SHREECEM","ACC","DALBHARAT","DEEPAKNTR","AARTIIND",
    "KPITTECH","LTTS","OFSS","NHPC","SJVN","CESC","IGL","AUBANK","BANDHANBNK","INDIANB",
    "PFC","RECLTD","ABCAPITAL","LTF","MANAPPURAM","LICHSGFIN","IDEA","TATACONSUM","APOLLOTYRE","ESCORTS"
]

@st.cache_data(ttl=86400)
def get_token_map():
    tmap = {}
    try:
        res = requests.get("https://angelbroking.com", timeout=25).json()
        for r in res:
            if r.get("exch_seg") == "NSE" and str(r.get("symbol", "")).endswith("-EQ"):
                tmap[r["name"]] = str(r["token"])
    except Exception:
        pass
    return tmap

@st.cache_data(ttl=600)
def get_technicals_and_charts(t):
    tickers = [f"{s}.NS" for s in ALL_FNO_STOCKS]
    intra_list, daily_list = [], []
    for i in range(0, len(tickers), 55):
        chunk = tickers[i:i+55]
        intra_list.append(yf.download(chunk, period="5d", interval=t, group_by='ticker', progress=False, threads=True))
        daily_list.append(yf.download(chunk, period="15d", interval="1d", group_by='ticker', progress=False, threads=True))
    intra, daily = pd.concat(intra_list, axis=1), pd.concat(daily_list, axis=1)
    tech_data, charts = {}, {}
    cols = intra.columns.get_level_values(0) if isinstance(intra.columns, pd.MultiIndex) else []

    for name in ALL_FNO_STOCKS:
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
            vol_b = round(float(df['Volume'].iloc[-1]) / float(df['Volume'].tail(20).mean()), 2)
            tech_data[name] = {
                "ema": float(df['EMA_20'].iloc[-1]), "vwap": float(df['VWAP'].iloc[-1]),
                "rsi": float(df['RSI'].iloc[-1]), "atr": float(df['ATR'].iloc[-1]), "vol_b": vol_b,
                "open": float(ddf['Open'].iloc[-1]), "high": float(ddf['High'].iloc[-1]),
                "low": float(ddf['Low'].iloc[-1]), "prev_c": float(ddf['Close'].iloc[-2]), "ltp": float(df['Close'].iloc[-1])
            }
        except Exception: pass
    return tech_data, charts

def get_realtime_snapshot(tech_data, c, r_pct, ratio):
    tmap = get_token_map()
    quotes, status = {}, "Yahoo Feed 🟡"
    ak, cc, mp, ts = st.secrets.get("API_KEY",""), st.secrets.get("CLIENT_CODE",""), st.secrets.get("MPIN",""), st.secrets.get("TOTP_SECRET","")
    if ak and cc and mp and ts and tmap:
        try:
            api = SmartConnect(api_key=ak)
            if api.generateSession(cc, mp, pyotp.TOTP(ts).now())['status']:
                tokens = [tmap[s] for s in tech_data.keys() if s in tmap]
                for i in range(0, len(tokens), 50):
                    q = api.getMarketData("OHLC", {"NSE": tokens[i:i+50]})
                    if q and q.get("status") and "fetched" in q.get("data", {}):
                        for it in q["data"]["fetched"]: quotes[str(it["symbolToken"])] = it
                status = f"Angel One Live Stream ({len(quotes)} F&O) 🟢"
        except Exception: pass

    rows, max_risk = [], (c * r_pct) / 100.0
    for name, td in tech_data.items():
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

        if ltp > td["ema"] and chg > 0.25:
            sig, sl, tgt = "🟢 BUY", round(ltp - sl_pts, 2), round(ltp + (sl_pts * ratio), 2)
        elif ltp < td["ema"] and chg < -0.25:
            sig, sl, tgt = "🔴 SELL", round(ltp + sl_pts, 2), round(ltp - (sl_pts * ratio), 2)
        else:
            sig, sl, tgt, qty = "⚪ WAIT", "-", "-", "-"

        rows.append({
            "Stock": name, "LTP (₹)": round(ltp, 2), "Change (%)": round(chg, 2),
            "Open": round(opn, 2), "High": round(high, 2), "Low": round(low, 2), "Prev Close": round(prev_c, 2),
            "Signal": sig, "Safe Qty": qty, "Stop-Loss": sl, "Target": tgt,
            "Vol Boost": td["vol_b"], "RSI": round(td["rsi"], 1), "VWAP": round(td["vwap"], 2)
        })
    return pd.DataFrame(rows), status

with st.spinner("Loading All 160+ NSE F&O Option Chain Stocks..."):
    tech_data, charts = get_technicals_and_charts(tf)
    df, status = get_realtime_snapshot(tech_data, cap, risk_pct, rr)

st.caption(f"Feed: **{status}** | Scanned: **{len(df)} F&O Stocks** | Max Risk: **₹{int(cap * risk_pct / 100):,}**")
view = st.radio("View", ["📊 Top 20 Gainers & Losers (OHLC + Signals)", "🖥️ 3-Column Pro Trader Terminal", "💥 Volume Spike Screener"], horizontal=True, label_visibility="collapsed")

if not df.empty:
    if view == "📊 Top 20 Gainers & Losers (OHLC + Signals)":
        st.subheader("🚀 Top 20 F&O Gainers (Real-Time OHLC + Buy/Sell Signals)")
        g20 = df.sort_values("Change (%)", ascending=False).head(20)
        st.dataframe(g20[["Stock", "LTP (₹)", "Change (%)", "Open", "High", "Low", "Prev Close", "Signal", "Safe Qty", "Stop-Loss", "Target"]], use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("📉 Top 20 F&O Losers (Real-Time OHLC + Buy/Sell Signals)")
        l20 = df.sort_values("Change (%)", ascending=True).head(20)
        st.dataframe(l20[["Stock", "LTP (₹)", "Change (%)", "Open", "High", "Low", "Prev Close", "Signal", "Safe Qty", "Stop-Loss", "Target"]], use_container_width=True, hide_index=True)

    elif view == "🖥️ 3-Column Pro Trader Terminal":
        col_left, col_mid, col_right = st.columns([2.2, 5.5, 2.3])
        with col_left:
            st.markdown("#### 📋 Live Watchlist")
            sel = st.selectbox("Select Stock:", sorted(df["Stock"].tolist()), label_visibility="collapsed")
            top_movers = pd.concat([df.sort_values("Change (%)", ascending=False).head(10), df.sort_values("Change (%)", ascending=True).head(10)])
            st.dataframe(top_movers[["Stock", "LTP (₹)", "Change (%)"]], use_container_width=True, hide_index=True)

        ri = df[df["Stock"] == sel].iloc[0]
        with col_mid:
            st.markdown(f"#### 🕯️ {sel} Live Chart (20 EMA + VWAP + RSI)")
            st.link_button(f"↗️ Open {sel} Superchart on TradingView", f"https://tradingview.com{sel.replace('&','_').replace('-','_')}/", use_container_width=True)
            if sel in charts:

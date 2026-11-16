import requests, pyotp
import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from SmartApi import SmartConnect

st.set_page_config(page_title="TradeFinder Pro Workspace", page_icon="💠", layout="wide")

if "theme_mode" not in st.session_state: st.session_state.theme_mode = "Dark"
if "chart_plat" not in st.session_state: st.session_state.chart_plat = "TradingView"

if st.session_state.theme_mode == "Dark":
    st.markdown("<style>.stApp{background-color:#0b0f19;color:#f8fafc}div[data-testid='stMetric']{background-color:#131a2a;border:1px solid #1e293b;padding:10px;border-radius:10px}</style>", unsafe_allow_html=True)
    p_bg, p_temp = "#0b0f19", "plotly_dark"
else:
    st.markdown("<style>.stApp{background-color:#f8fafc;color:#0f172a}section[data-testid='stSidebar']{background-color:#ffffff}div[data-testid='stMetric']{background-color:#ffffff;border:1px solid #cbd5e1;padding:10px;border-radius:10px;color:#0f172a}h1,h2,h3,h4,p,span,label{color:#0f172a !important}</style>", unsafe_allow_html=True)
    p_bg, p_temp = "#f8fafc", "plotly_white"

st.sidebar.markdown("## 💠 TradeFinder Pro")
st.sidebar.success("🔴 LIVE STREAMING (Auto-Updates Every 5s)")
page = st.sidebar.radio("NAVIGATION", ["⚡ Market Pulse", "📊 Sector Scope", "🔥 Insider Heatmap", "🏦 FII / DII & Index", "🕯️ Live Chart & Risk", "⚙️ Settings"])
st.sidebar.divider()
cap = st.sidebar.number_input("Total Capital (₹)", 5000, 5000000, 30000, 5000)
risk_pct = st.sidebar.slider("Risk / Trade (%)", 0.5, 5.0, 1.0, 0.5)
rr = st.sidebar.selectbox("Risk : Reward", [1.5, 2.0, 2.5, 3.0], index=1)
tf = st.sidebar.selectbox("Timeframe", ["5m", "15m", "1h"], index=1)

SEC_MAP = {
    "HDFCBANK":"Banking","ICICIBANK":"Banking","SBIN":"Banking","AXISBANK":"Banking","KOTAKBANK":"Banking","INDUSINDBK":"Banking","BANKBARODA":"Banking","PNB":"Banking","CANBK":"Banking","FEDERALBNK":"Banking","IDFCFIRSTB":"Banking","AUBANK":"Banking",
    "BAJFINANCE":"Finance","BAJAJFINSV":"Finance","CHOLAFIN":"Finance","SHRIRAMFIN":"Finance","PFC":"Finance","RECLTD":"Finance","SBILIFE":"Finance","HDFCLIFE":"Finance","JIOFIN":"Finance","MUTHOOTFIN":"Finance","ICICIGI":"Finance",
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
def get_tokens():
    tmap = {}
    try:
        for r in requests.get("https://angelbroking.com", timeout=25).json():
            if r.get("exch_seg") == "NSE" and str(r.get("symbol", "")).endswith("-EQ"): tmap[r["name"]] = str(r["token"])
    except Exception: pass
    return tmap

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

@st.cache_data(ttl=600)
def load_base(t):
    stocks = list(SEC_MAP.keys())
    tickers = [f"{s}.NS" for s in stocks]
    intra_l, daily_l = [], []
    for i in range(0, len(tickers), 50):
        ch = tickers[i:i+50]
        intra_l.append(yf.download(ch, period="5d", interval=t, group_by='ticker', progress=False, threads=True))
        daily_l.append(yf.download(ch, period="10d", interval="1d", group_by='ticker', progress=False, threads=True))
    intra, daily = pd.concat(intra_l, axis=1), pd.concat(daily_l, axis=1)
    tech, charts = {}, {}
    cols = intra.columns.get_level_values(0) if isinstance(intra.columns, pd.MultiIndex) else []
    for name in stocks:
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
            avg_v, cur_v = float(df['Volume'].tail(20).mean()), float(df['Volume'].iloc[-1])
            vol_b = round(cur_v / avg_v, 2) if avg_v > 0 else 1.0
            tech[name] = {"sec":SEC_MAP[name],"ema":float(df['EMA_20'].iloc[-1]),"vwap":float(df['VWAP'].iloc[-1]),"rsi":float(df['RSI'].iloc[-1]),"atr":float(df['ATR'].iloc[-1]),"vol_b":vol_b,"open":float(ddf['Open'].iloc[-1]),"high":float(ddf['High'].iloc[-1]),"low":float(ddf['Low'].iloc[-1]),"prev_c":float(ddf['Close'].iloc[-2]),"ltp":float(df['Close'].iloc[-1])}
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
                status = f"Angel One 0-Sec Live ({len(quotes)} F&O) 🟢"
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
        rows.append({"Stock":name,"Sector":td["sec"],"LTP":round(ltp,2),"Chg %":round(chg,2),"Open":round(opn,2),"High":round(high,2),"Low":round(low,2),"Signal":sig,"Qty":qty,"SL":sl,"Target":tgt,"Boost (x)":td["vol_b"],"RSI":round(td["rsi"],1),"VWAP":round(td["vwap"],2)})
    return pd.DataFrame(rows), status

idx = get_indices()
if idx:
    cols = st.columns(len(idx))
    for i, (k, (v, ch)) in enumerate(idx.items()): cols[i].metric(k, f"{v:,}", f"{ch}%")

tech_data, charts = load_base(tf)

@st.fragment(run_every=5)
def render_live_workspace():
    df, status = get_live_df(tech_data, cap, risk_pct, rr)
    c_h, c_b = st.columns(2)
    c_h.caption(f"Feed: **{status}** | Auto-Updating Every 5s | Theme: **{st.session_state.theme_mode}** | Chart: **{st.session_state.chart_plat}**")
    if c_b.button("🔄 Reset Cache", use_container_width=True): st.cache_data.clear()

    if not df.empty:
        ql1, ql2 = st.columns([3, 1.5])
        sel_stock = ql1.selectbox("Select Stock:", sorted(df["Stock"].tolist()), label_visibility="collapsed")
        tv_s = sel_stock.replace("&", "_").replace("-", "_")
        chart_url = f"https://tradingview.com:{tv_s}" if st.session_state.chart_plat == "TradingView" else "https://angelone.in"
        ql2.markdown(f'<a href="{chart_url}" target="_blank" style="display:block;text-align:center;background-color:#2563eb;color:white;padding:9px;border-radius:8px;text-decoration:none;font-weight:600;">↗️ Open {sel_stock} on {st.session_state.chart_plat}</a>', unsafe_allow_html=True)

        if page == "⚙️ Settings":
            st.subheader("⚙️ Preferences & Settings")
            s1, s2 = st.columns(2)
            with s1:
                st.markdown("#### 🎨 Preferred Display Mode")
                new_theme = st.radio("Theme", ["Dark", "Light"], index=0 if st.session_state.theme_mode=="Dark" else 1)
                if new_theme != st.session_state.theme_mode:
                    st.session_state.theme_mode = new_theme
                    st.rerun()
            with s2:
                st.markdown("#### 📈 Chart Platform Selection")
                new_plat = st.radio("Platform", ["TradingView", "Angel One"], index=0 if st.session_state.chart_plat=="TradingView" else 1)
                if new_plat != st.session_state.chart_plat:
                    st.session_state.chart_plat = new_plat
                    st.rerun()

        elif page == "⚡ Market Pulse":
            c1, c2 = st.columns(2)
            c1.subheader("🚀 Top 20 Gainers")
            c1.dataframe(df.sort_values("Chg %", ascending=False).head(20)[["Stock","LTP","Chg %","Open","High","Low","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)
            c2.subheader("📉 Top 20 Losers")
            c2.dataframe(df.sort_values("Chg %", ascending=True).head(20)[["Stock","LTP","Chg %","Open","High","Low","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)
            st.divider()
            b1, b2 = st.columns(2)
            b1.subheader("💥 Intraday Boost (Volume Spike)")
            b1.dataframe(df.sort_values("Boost (x)", ascending=False).head(15)[["Stock","Sector","LTP","Chg %","Boost (x)","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)
            b2.subheader("🎯 Breakout Beacon (EMA + Momentum)")
            b2.dataframe(df[df["Signal"] != "⚪ WAIT"].sort_values("Boost (x)", ascending=False).head(15)[["Stock","Sector","LTP","Chg %","RSI","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)

        elif page == "📊 Sector Scope":
            st.subheader("📊 Sector Scope (Where Institutions Are Buying & Selling)")
            sec_df = df.groupby("Sector").agg(Avg_Chg=("Chg %", "mean"), Total_Boost=("Boost (x)", "mean"), Stocks=("Stock", "count")).reset_index().sort_values("Avg_Chg", ascending=False)
            sec_df["Avg_Chg"] = sec_df["Avg_Chg"].round(2)
            fig_bar = px.bar(sec_df, x="Sector", y="Avg_Chg", color="Avg_Chg", color_continuous_scale=['#ef4444', '#22c55e'], text="Avg_Chg", title="Daily Sector Score (Green = Buying | Red = Selling)")
            fig_bar.update_layout(height=360, paper_bgcolor=p_bg, template=p_temp)
            st.plotly_chart(fig_bar, use_container_width=True)
            sec_sel = st.selectbox("🔍 Drill-Down into Sector Stocks:", sec_df["Sector"].tolist())
            st.dataframe(df[df["Sector"] == sec_sel].sort_values("Chg %", ascending=False)[["Stock","LTP","Chg %","Boost (x)","RSI","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)

        elif page == "🔥 Insider Heatmap":
            st.subheader("🔥 Live Sector & Stock Momentum Heatmap")
            df["Box"] = df["Chg %"].abs() + 0.3
            fig = px.treemap(df, path=['Sector', 'Stock'], values='Box', color='Chg %', color_continuous_scale=['#ef4444', '#64748b', '#22c55e'], color_continuous_midpoint=0, hover_data=['LTP','Boost (x)','Signal'])
            fig.update_layout(height=550, margin=dict(t=10,l=10,r=10,b=10), paper_bgcolor=p_bg)
            st.plotly_chart(fig, use_container_width=True)

        elif page == "🏦 FII / DII & Index":
            st.subheader("🏦 FII / DII Cash Market & Index Activity")
            f1, f2 = st.columns(2)
            f1.markdown('<a href="https://nseindia.com" target="_blank" style="display:block;text-align:center;background-color:#1e293b;color:white;padding:10px;border-radius:8px;text-decoration:none;border:1px solid #334155;">↗️ Open Live FII / DII Data on NSE India</a>', unsafe_allow_html=True)
            f2.markdown('<a href="https://nseindia.com" target="_blank" style="display:block;text-align:center;background-color:#1e293b;color:white;padding:10px;border-radius:8px;text-decoration:none;border:1px solid #334155;">↗️ Open Live Nifty Option Chain (OI / PCR)</a>', unsafe_allow_html=True)
            st.divider()
            st.subheader("📈 Nifty 50 & Banking Heavyweights Contribution")
            heavy = df[df["Sector"].isin(["Banking", "IT", "Energy"])].sort_values("Chg %", ascending=False)
            st.dataframe(heavy[["Stock","Sector","LTP","Chg %","Boost (x)","Signal","Qty","SL","Target"]], use_container_width=True, hide_index=True)

        elif page == "🕯️ Live Chart & Risk":
            ri = df[df["Stock"] == sel_stock].iloc
            m = st.columns(6)
            m.metric("LTP", f"₹{ri['LTP']}", f"{ri['Chg %']}%")
            m.metric("VWAP", f"₹{ri['VWAP']}")
            m.metric("Signal", ri['Signal'])
            m.metric("Safe Qty", f"{ri['Qty']}")
            m.metric("Stop-Loss", f"₹{ri['SL']}")
            m.metric("Target", f"₹{ri['Target']}")
            if sel_stock in charts:
                cdf = charts[sel_stock].tail(75)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.72, 0.28])
                fig.add_trace(go.Candlestick(x=cdf.index, open=cdf['Open'], high=cdf['High'], low=cdf['Low'], close=cdf['Close'], name="Price"), row=1, col=1)
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['EMA_20'], mode='lines', line=dict(color='#f59e0b', width=2), name="20 EMA"), row=1, col=1)
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['VWAP'], mode='lines', line=dict(color='#8b5cf6', width=2, dash='dot'), name="VWAP"), row=1, col=1)
                fig.add_trace(go.Scatter(x=cdf.index, y=cdf['RSI'], mode='lines', line=dict(color='#0284c7', width=1.8), name="RSI"), row=2, col=1)
                fig.update_layout(height=520, xaxis_rangeslider_visible=False, template=p_temp, paper_bgcolor=p_bg)
                st.plotly_chart(fig, use_container_width=True)

render_live_workspace()

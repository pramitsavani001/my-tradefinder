import time, re, urllib.parse, datetime as dt
import numpy as np, pandas as pd, pyotp, streamlit as st, yfinance as yf
import plotly.express as px, plotly.graph_objects as go
from SmartApi import SmartConnect
import config as C, strategy as S

st.set_page_config(page_title="TradeFlow Pro – Personal TradeFinder", page_icon="⚡", layout="wide")

# Custom CSS for dark professional dashboard look
st.markdown("""
<style>
    .metric-card {background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

st.title("⚡ TradeFlow Pro – All-in-One Market Scanner")

# Sidebar Navigation like TradeFinder
menu = st.sidebar.radio("📌 Select Scanner Module", [
    "🔥 Market Pulse (Gainers/Losers/BO)",
    "📊 Sector Scope (Heatmap)",
    "⚡ Option Clock (Live OI Flow)",
    "🎯 Insider Strategy (2D BO & NR7)",
    "🌊 Swing Spectrum (10D/50D BO)",
    "📈 Index Mover (Nifty Contributors)"
])

st.sidebar.divider()
cap = st.sidebar.number_input("Capital (₹)", 5000, 5000000, C.CAPITAL, 5000)
risk = st.sidebar.slider("Risk per trade (%)", 0.25, 3.0, C.RISK_PCT, 0.25)
if st.sidebar.button("🔄 Refresh Market Data"):
    st.cache_data.clear()

def tv_url(sym):
    clean = sym.replace("&", "_").replace("-", "_")
    return f"https://tradingview.com{urllib.parse.quote(clean)}"

# Fetch daily & intraday data for all Universe stocks using yfinance (works 24/7 even when market is closed)
@st.cache_data(ttl=900)
def load_market_data():
    tickers = [f"{s}.NS" for s in C.UNIVERSE]
    df = yf.download(tickers, period="60d", interval="1d", group_by="ticker", progress=False, threads=True)
    rows = []
    for sym in C.UNIVERSE:
        tk = f"{sym}.NS"
        try:
            sub = df[tk].dropna()
            if len(sub) < 15: continue
            c_now = float(sub["Close"].iloc[-1])
            c_prev = float(sub["Close"].iloc[-2])
            h_now = float(sub["High"].iloc[-1])
            l_now = float(sub["Low"].iloc[-1])
            v_now = float(sub["Volume"].iloc[-1])
            v_avg20 = float(sub["Volume"].iloc[-21:-1].mean())
            chg_pct = ((c_now - c_prev) / c_prev) * 100
            rvol = round(v_now / v_avg20, 2) if v_avg20 > 0 else 0
            
            # 2-Day High/Low
            h_2d = float(sub["High"].iloc[-3:-1].max())
            l_2d = float(sub["Low"].iloc[-3:-1].min())
            
            # 10-Day & 50-Day High/Low
            h_10d = float(sub["High"].iloc[-11:-1].max())
            l_10d = float(sub["Low"].iloc[-11:-1].min())
            h_50d = float(sub["High"].iloc[-51:-1].max()) if len(sub) >= 51 else h_10d
            l_50d = float(sub["Low"].iloc[-51:-1].min()) if len(sub) >= 51 else l_10d
            
            # NR7 (Narrowest Range of last 7 days)
            ranges = (sub["High"] - sub["Low"]).iloc[-7:]
            is_nr7 = bool(ranges.iloc[-1] == ranges.min())
            
            rows.append({
                "Symbol": sym,
                "Sector": C.SYMBOL_SECTOR.get(sym, "Other"),
                "Price": round(c_now, 2),
                "Change %": round(chg_pct, 2),
                "RVOL": rvol,
                "Chart": tv_url(sym),
                "BO_2D": "2D High BO" if c_now > h_2d else ("2D Low BO" if c_now < l_2d else "-"),
                "BO_10D": "10D High BO" if c_now > h_10d else ("10D Low BO" if c_now < l_10d else "-"),
                "BO_50D": "50D High BO" if c_now > h_50d else ("50D Low BO" if c_now < l_50d else "-"),
                "NR7": "Yes" if is_nr7 else "No",
                "Day_Pos": round(((c_now - l_now) / (h_now - l_now)) * 100, 1) if h_now > l_now else 50.0
            })
        except Exception:
            continue
    return pd.DataFrame(rows)

col_cfg = {"Chart": st.column_config.LinkColumn("Chart", display_text="📈 Open TV")}

# ==================== MODULE 1: MARKET PULSE ====================
if menu == "🔥 Market Pulse (Gainers/Losers/BO)":
    st.subheader("🔥 Market Pulse – Momentum, Gainers, Losers & High Power Stocks")
    with st.spinner("Scanning NSE F&O Universe..."):
        mdf = load_market_data()
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🚀 Top Gainers")
        gainers = mdf.sort_values("Change %", ascending=False).head(15)[["Symbol", "Sector", "Price", "Change %", "RVOL", "Chart"]]
        st.dataframe(gainers, column_config=col_cfg, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("### 🔻 Top Losers")
        losers = mdf.sort_values("Change %", ascending=True).head(15)[["Symbol", "Sector", "Price", "Change %", "RVOL", "Chart"]]
        st.dataframe(losers, column_config=col_cfg, use_container_width=True, hide_index=True)
        
    st.divider()
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("### ⚡ High Power Stocks (High Relative Volume > 1.5x)")
        hp = mdf[mdf["RVOL"] >= 1.5].sort_values("RVOL", ascending=False)[["Symbol", "Sector", "Price", "Change %", "RVOL", "Chart"]]
        st.dataframe(hp, column_config=col_cfg, use_container_width=True, hide_index=True)
    with c4:
        st.markdown("### 🎯 Near Day High / Day Low (Strong Close)")
        extremes = mdf[(mdf["Day_Pos"] >= 90) | (mdf["Day_Pos"] <= 10)].sort_values("Change %", ascending=False)[["Symbol", "Price", "Change %", "Day_Pos", "Chart"]]
        st.dataframe(extremes, column_config=col_cfg, use_container_width=True, hide_index=True)

# ==================== MODULE 2: SECTOR SCOPE ====================
elif menu == "📊 Sector Scope (Heatmap)":
    st.subheader("📊 Sector Scope – Sector Performance & Heatmap")
    with st.spinner("Calculating Sector Strength..."):
        mdf = load_market_data()
    
    sec_df = mdf.groupby("Sector").agg(
        Avg_Change=("Change %", "mean"),
        Avg_RVOL=("RVOL", "mean"),
        Advancing=("Change %", lambda x: (x > 0).sum()),
        Declining=("Change %", lambda x: (x < 0).sum())
    ).reset_index().sort_values("Avg_Change", ascending=False)
    
    fig = px.bar(sec_df, x="Sector", y="Avg_Change", color="Avg_Change",
                 color_continuous_scale=["#ff4b4b", "#808080", "#00cc66"],
                 title="Sector Performance (% Change)", text_auto=".2f")
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("### 🔍 Drill-Down by Sector")
    sel_sec = st.selectbox("Select Sector to view stocks:", sec_df["Sector"].tolist())
    sub_sec = mdf[mdf["Sector"] == sel_sec].sort_values("Change %", ascending=False)[["Symbol", "Price", "Change %", "RVOL", "BO_2D", "Chart"]]
    st.dataframe(sub_sec, column_config=col_cfg, use_container_width=True, hide_index=True)

# ==================== MODULE 3: OPTION CLOCK (ANGEL ONE LIVE OI) ====================
elif menu == "⚡ Option Clock (Live OI Flow)":
    st.subheader("⚡ Option Clock – Live Option OI & PCR Scanner (Angel One API)")
    
    @st.cache_resource
    def angel_login():
        api = SmartConnect(api_key=C.API_KEY, timeout=25)
        r = api.generateSession(C.CLIENT_CODE, C.PIN, pyotp.TOTP(C.TOTP_SECRET).now())
        if not r or not r.get("status"): raise RuntimeError(f"Login failed: {r}")
        return api

    def safe_search(api, exch, query):
        for _ in range(2):
            try:
                time.sleep(0.35)
                r = api.searchScrip(exch, query)
                if r and r.get("status") and r.get("data"): return r["data"]
            except Exception: time.sleep(1)
        return []

    @st.cache_data(ttl=86400)
    def build_opt_master(_api):
        rows = []
        top_list = ["NIFTY", "BANKNIFTY", "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS", "TATAMOTORS", "LT", "AXISBANK", "BAJFINANCE", "BHARTIARTL", "ITC", "SUNPHARMA", "MARUTI", "TATASTEEL", "HAL", "BEL", "ADANIENT"]
        for u in top_list:
            if u not in C.INDEX_TOKENS:
                for item in safe_search(_api, "NSE", f"{u}-EQ"):
                    if item.get("tradingsymbol") == f"{u}-EQ":
                        rows.append({"token": str(item["symboltoken"]), "symbol": f"{u}-EQ", "name": u, "exch_seg": "NSE"})
                        break
            for item in safe_search(_api, "NFO", u):
                tsym = item.get("tradingsymbol", "")
                if re.match(rf"^{re.escape(u)}\d{{2}}[A-Z]{{3}}\d{{2}}\d+(\.\d+)?(CE|PE)$", tsym):
                    rows.append({"token": str(item["symboltoken"]), "symbol": tsym, "name": u, "exch_seg": "NFO"})
        return pd.DataFrame(rows)

    def fetch_quotes(api, exch, tokens, mode="FULL"):
        out = []
        for i in range(0, len(tokens), 50):
            try:
                time.sleep(0.45)
                r = api.getMarketData(mode, {exch: tokens[i:i+50]})
                if r and r.get("status"): out += r["data"].get("fetched", [])
            except Exception: pass
        return out

    try:
        api = angel_login()
        with st.spinner("Loading Live Option Chain Tokens..."):
            m = build_opt_master(api)
        eq_df = m[(m.exch_seg == "NSE") & (m.symbol.str.endswith("-EQ"))]
        eq_map = dict(zip(eq_df.name, eq_df.token.astype(str)))
        unders = list(m[m.exch_seg == "NFO"].name.unique())
        sp_tokens = {u: (C.INDEX_TOKENS.get(u) or eq_map.get(u)) for u in unders if (C.INDEX_TOKENS.get(u) or eq_map.get(u))}
        
        q_spot = fetch_quotes(api, "NSE", list(sp_tokens.values()), "LTP")
        tok2u = {v: k for k, v in sp_tokens.items()}
        spot = {tok2u[str(x["symbolToken"])]: float(x["ltp"]) for x in q_spot if str(x["symbolToken"]) in tok2u}
        
        contracts = []
        for u, p in spot.items():
            o = m[(m.exch_seg == "NFO") & (m.name == u)].copy()
            pat = rf"^{re.escape(u)}(\d{{2}}[A-Z]{{3}}\d{{2}})(\d+(?:\.\d+)?)(CE|PE)$"
            ext = o.symbol.str.extract(pat)

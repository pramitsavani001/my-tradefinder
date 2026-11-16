import time, re, urllib.parse
import numpy as np, pandas as pd, pyotp, streamlit as st, yfinance as yf
import plotly.express as px, plotly.graph_objects as go
from SmartApi import SmartConnect
import config as C

st.set_page_config(page_title="TradeFlow Pro", page_icon="⚡", layout="wide")
st.title("⚡ TradeFlow Pro – All-in-One Market Scanner")

menu = st.sidebar.radio("📌 Select Scanner", [
    "🔥 Market Pulse",
    "📊 Sector Scope",
    "⚡ Option Clock",
    "🎯 Insider Strategy",
    "🌊 Swing Spectrum",
    "📈 Index Mover"
])

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()

def tv_url(sym):
    clean = sym.replace("&", "_").replace("-", "_")
    return f"https://tradingview.com{urllib.parse.quote(clean)}"

col_cfg = {"Chart": st.column_config.LinkColumn("Chart", display_text="📈 Open TV")}

@st.cache_data(ttl=900)
def load_market_data():
    tickers = [f"{s}.NS" for s in C.UNIVERSE]
    df = yf.download(tickers, period="60d", interval="1d", group_by="ticker", progress=False, threads=True)
    rows = []
    for sym in C.UNIVERSE:
        try:
            sub = df[f"{sym}.NS"].dropna()
            if len(sub) < 15:
                continue
            c_now = float(sub["Close"].values.item(-1))
            c_prev = float(sub["Close"].values.item(-2))
            h_now = float(sub["High"].values.item(-1))
            l_now = float(sub["Low"].values.item(-1))
            v_now = float(sub["Volume"].values.item(-1))
            v_avg = float(sub["Volume"].head(len(sub) - 1).tail(20).mean())
            chg = ((c_now - c_prev) / c_prev) * 100
            rvol = round(v_now / v_avg, 2) if v_avg > 0 else 0
            prev = sub.head(len(sub) - 1)
            h2, l2 = float(prev["High"].tail(2).max()), float(prev["Low"].tail(2).min())
            h10, l10 = float(prev["High"].tail(10).max()), float(prev["Low"].tail(10).min())
            h50, l50 = float(prev["High"].tail(50).max()), float(prev["Low"].tail(50).min())
            rng = (sub["High"] - sub["Low"]).tail(7)
            nr7 = "Yes" if rng.values.item(-1) == rng.min() else "No"
            dpos = round(((c_now - l_now) / (h_now - l_now)) * 100, 1) if h_now > l_now else 50.0
            rows.append({
                "Symbol": sym, "Sector": C.SYMBOL_SECTOR.get(sym, "Other"),
                "Price": round(c_now, 2), "Change %": round(chg, 2), "RVOL": rvol,
                "Chart": tv_url(sym),
                "BO_2D": "2D High BO" if c_now > h2 else ("2D Low BO" if c_now < l2 else "-"),
                "BO_10D": "10D High BO" if c_now > h10 else ("10D Low BO" if c_now < l10 else "-"),
                "BO_50D": "50D High BO" if c_now > h50 else ("50D Low BO" if c_now < l50 else "-"),
                "NR7": nr7, "Day_Pos": dpos
            })
        except Exception:
            continue
    return pd.DataFrame(rows)

if menu == "🔥 Market Pulse":
    st.subheader("🔥 Market Pulse – Gainers, Losers & High Power Stocks")
    mdf = load_market_data()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🚀 Top Gainers")
        st.dataframe(mdf.sort_values("Change %", ascending=False).head(15)[["Symbol", "Sector", "Price", "Change %", "RVOL", "Chart"]], column_config=col_cfg, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("### 🔻 Top Losers")
        st.dataframe(mdf.sort_values("Change %", ascending=True).head(15)[["Symbol", "Sector", "Price", "Change %", "RVOL", "Chart"]], column_config=col_cfg, use_container_width=True, hide_index=True)
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("### ⚡ High Power Stocks (RVOL > 1.5x)")
        st.dataframe(mdf[mdf["RVOL"] >= 1.5].sort_values("RVOL", ascending=False)[["Symbol", "Sector", "Price", "Change %", "RVOL", "Chart"]], column_config=col_cfg, use_container_width=True, hide_index=True)
    with c4:
        st.markdown("### 🎯 Day High / Low Extremes")
        st.dataframe(mdf[(mdf["Day_Pos"] >= 90) | (mdf["Day_Pos"] <= 10)].sort_values("Change %", ascending=False)[["Symbol", "Price", "Change %", "Day_Pos", "Chart"]], column_config=col_cfg, use_container_width=True, hide_index=True)

elif menu == "📊 Sector Scope":
    st.subheader("📊 Sector Scope – Sector Performance")
    mdf = load_market_data()
    sec = mdf.groupby("Sector").agg(Avg_Change=("Change %", "mean"), Avg_RVOL=("RVOL", "mean")).reset_index().sort_values("Avg_Change", ascending=False)
    fig = px.bar(sec, x="Sector", y="Avg_Change", color="Avg_Change", color_continuous_scale=["#ff4b4b", "#808080", "#00cc66"], text_auto=".2f")
    st.plotly_chart(fig, use_container_width=True)
    sel = st.selectbox("Select Sector:", sec["Sector"].tolist())
    st.dataframe(mdf[mdf["Sector"] == sel].sort_values("Change %", ascending=False)[["Symbol", "Price", "Change %", "RVOL", "BO_2D", "Chart"]], column_config=col_cfg, use_container_width=True, hide_index=True)

elif menu == "⚡ Option Clock":
    st.subheader("⚡ Option Clock – Live Option OI & PCR (Angel One)")
    @st.cache_resource
    def get_api():
        api = SmartConnect(api_key=C.API_KEY, timeout=25)
        r = api.generateSession(C.CLIENT_CODE, C.PIN, pyotp.TOTP(C.TOTP_SECRET).now())
        if not r or not r.get("status"):
            raise RuntimeError(f"Login failed: {r}")
        return api

    @st.cache_data(ttl=86400)
    def get_opt_tokens(_api):
        rows = []
        stocks = ["NIFTY", "BANKNIFTY", "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS", "TATAMOTORS", "LT", "AXISBANK", "BAJFINANCE", "BHARTIARTL", "ITC", "SUNPHARMA", "MARUTI", "TATASTEEL", "HAL", "BEL", "ADANIENT"]
        for u in stocks:
            if u not in C.INDEX_TOKENS:
                time.sleep(0.35)
                rn = _api.searchScrip("NSE", f"{u}-EQ")
                for it in (rn.get("data") or []):
                    if it.get("tradingsymbol") == f"{u}-EQ":
                        rows.append({"token": str(it["symboltoken"]), "symbol": f"{u}-EQ", "name": u, "exch": "NSE"})
                        break
            time.sleep(0.35)
            rf = _api.searchScrip("NFO", u)
            for it in (rf.get("data") or []):
                ts = it.get("tradingsymbol", "")
                if re.match(rf"^{re.escape(u)}\d{{2}}[A-Z]{{3}}\d{{2}}\d+(\.\d+)?(CE|PE)$", ts):
                    rows.append({"token": str(it["symboltoken"]), "symbol": ts, "name": u, "exch": "NFO"})
        return pd.DataFrame(rows)

    try:
        api = get_api()
        m = get_opt_tokens(api)
        eq = m[m.exch == "NSE"]
        eq_map = dict(zip(eq.name, eq.token))
        unders = list(m[m.exch == "NFO"].name.unique())
        sp_tok = {u: (C.INDEX_TOKENS.get(u) or eq_map.get(u)) for u in unders if (C.INDEX_TOKENS.get(u) or eq_map.get(u))}
        q_sp = api.getMarketData("LTP", {"NSE": list(sp_tok.values())})["data"]["fetched"]
        tok2u = {v: k for k, v in sp_tok.items()}
        spot = {tok2u[str(x["symbolToken"])]: float(x["ltp"]) for x in q_sp if str(x["symbolToken"]) in tok2u}
        
        clist = []
        for u, p in spot.items():
            o = m[(m.exch == "NFO") & (m.name == u)].copy()
            ext = o.symbol.str.extract(rf"^{re.escape(u)}(\d{{2}}[A-Z]{{3}}\d{{2}})(\d+(?:\.\d+)?)(CE|PE)$")
            o["exp"] = pd.to_datetime(ext.get(0), format="%d%b%y", errors="coerce")
            o["k"] = pd.to_numeric(ext.get(1), errors="coerce")
            o["cp"] = ext.get(2)
            o = o.dropna(subset=["exp", "k", "cp"])
            o = o[o.exp >= pd.Timestamp.today().normalize()]
            if o.empty:
                continue
            o = o[o.exp == o.exp.min()]
            stks = sorted(o.k.unique())
            atm = min(stks, key=lambda x: abs(x - p))
            ia = stks.index(atm)
            nst = 5 if u in C.INDEX_TOKENS else 2
            sel_k = stks[max(0, ia - nst): ia + nst + 1]
            clist.append(o[o.k.isin(sel_k)].assign(und=u))
            
        allc = pd.concat(clist)
        info = allc.set_index("token")
        toks = list(allc.token.unique())
        fetched = []
        for i in range(0, len(toks), 50):
            time.sleep(0.45)
            r = api.getMarketData("FULL", {"NFO": toks[i:i+50]})
            if r and r.get("status"):
                fetched += r["data"].get("fetched", [])
        snap = []
        for x in fetched:
            tk = str(x["symbolToken"])
            if tk in info.index:
                r = info.loc[tk]
                if isinstance(r, pd.DataFrame):
                    r = r.head(1).squeeze()
                snap.append({"und": r.und, "cp": r.cp, "oi": float(x.get("opnInterest", 0))})
        df_oi = pd.DataFrame(snap).groupby(["und", "cp"]).oi.sum().unstack(fill_value=0)
        df_oi["PCR"] = (df_oi["PE"] / df_oi["CE"].replace(0, np.nan)).round(2).fillna(0)
        df_oi["Sentiment"] = df_oi["PCR"].apply(lambda x: "BULLISH 🟢" if x > 1.15 else ("BEARISH 🔴" if x < 0.85 else "NEUTRAL ⚪"))
        df_oi["Chart"] = [tv_url(u) for u in df_oi.index]
        
        fig = go.Figure(data=[
            go.Bar(name="Call OI", x=df_oi.index, y=df_oi["CE"], marker_color="#ff4b4b"),
            go.Bar(name="Put OI", x=df_oi.index, y=df_oi["PE"], marker_color="#00cc66")
        ])
        fig.update_layout(barmode="group", title="Call vs Put Open Interest")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_oi.rename(columns={"CE": "Call OI", "PE": "Put OI"}), column_config=col_cfg, use_container_width=True)
    except Exception as e:
        st.error(f"Option API Error: {e}")

elif menu == "🎯 Insider Strategy":
    st.subheader("🎯 Insider Strategy – 2-Day Breakouts & NR7")
    mdf = load_market_data()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🔥 2-Day Breakouts")

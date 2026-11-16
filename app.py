import time, re, urllib.parse
import numpy as np, pandas as pd, pyotp, streamlit as st, yfinance as yf
import plotly.express as px, plotly.graph_objects as go
from SmartApi import SmartConnect
import config as C

st.set_page_config(page_title="TradeFlow Pro AI", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .stApp {background-color: #0e1117;}
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 12px 16px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    h1, h2, h3 {color: #f0f6fc; font-family: 'Segoe UI', sans-serif;}
</style>
""", unsafe_allow_html=True)

st.title("⚡ TradeFlow Pro – High-Probability Setup Scanner")

menu = st.sidebar.radio("📌 Scanner Modules", [
    "🎯 High-Probability Setups",
    "🔥 Market Pulse (Gainers/Losers)",
    "📊 Sector Heatmap (Treemap)",
    "⚡ Option Clock (Live OI)",
    "🌊 Swing & Breakout Radar",
    "📈 Nifty Index Movers"
])

st.sidebar.divider()
if st.sidebar.button("🔄 Refresh Live Data"):
    st.cache_data.clear()

st.sidebar.caption("⚠️ શેરબજાર જોખમને આધીન છે. કોઈપણ ટ્રેડ લેતા પહેલા સ્ટોપ-લોસ (SL) અવશ્ય રાખવો.")

def tv_url(sym):
    clean = sym.replace("&", "_").replace("-", "_")
    return f"https://tradingview.com{urllib.parse.quote(clean)}"

col_cfg = {
    "Chart": st.column_config.LinkColumn("Chart", display_text="📈 Open"),
    "Setup Score": st.column_config.ProgressColumn("Setup Quality", min_value=0, max_value=100, format="%d%%")
}

def color_signal(val):
    v = str(val)
    if "BUY" in v:
        return "background-color: #0d4429; color: #3fb950; font-weight: bold;"
    elif "SELL" in v:
        return "background-color: #491217; color: #f85149; font-weight: bold;"
    return "color: #8b949e;"

def color_chg(val):
    try:
        num = float(val)
        if num > 0:
            return "color: #3fb950; font-weight: bold;"
        elif num < 0:
            return "color: #f85149; font-weight: bold;"
    except Exception:
        pass
    return ""

@st.cache_data(ttl=900)
def load_market_data():
    tickers = [f"{s}.NS" for s in C.UNIVERSE]
    df = yf.download(tickers, period="60d", interval="1d", group_by="ticker", progress=False, threads=True)
    rows = []
    for sym in C.UNIVERSE:
        try:
            sub = df[f"{sym}.NS"].dropna()
            if len(sub) < 52:
                continue
            close_s = sub["Close"]
            high_s = sub["High"]
            low_s = sub["Low"]
            vol_s = sub["Volume"]

            c_now = float(close_s.values.item(-1))
            c_prev = float(close_s.values.item(-2))
            h_now = float(high_s.values.item(-1))
            l_now = float(low_s.values.item(-1))
            v_now = float(vol_s.values.item(-1))
            v_avg = float(vol_s.head(len(sub) - 1).tail(20).mean())

            chg = ((c_now - c_prev) / c_prev) * 100
            rvol = round(v_now / v_avg, 2) if v_avg > 0 else 0

            ema20 = float(close_s.ewm(span=20).mean().values.item(-1))
            ema50 = float(close_s.ewm(span=50).mean().values.item(-1))

            delta = close_s.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = float((100 - (100 / (1 + rs))).fillna(50).values.item(-1))

            tr = pd.concat([high_s - low_s, (high_s - close_s.shift(1)).abs(), (low_s - close_s.shift(1)).abs()], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().values.item(-1))

            prev = sub.head(len(sub) - 1)
            h2, l2 = float(prev["High"].tail(2).max()), float(prev["Low"].tail(2).min())
            h10, l10 = float(prev["High"].tail(10).max()), float(prev["Low"].tail(10).min())
            h50, l50 = float(prev["High"].tail(50).max()), float(prev["Low"].tail(50).min())

            rng = (high_s - low_s).tail(7)
            nr7 = "Yes" if rng.values.item(-1) == rng.min() else "No"
            dpos = round(((c_now - l_now) / (h_now - l_now)) * 100, 1) if h_now > l_now else 50.0

            # Strict 4-Layer High-Probability Filter
            buy_cond = (c_now > ema20) and (ema20 > ema50) and (c_now > h2) and (rvol >= 1.5) and (58 <= rsi <= 75)
            sell_cond = (c_now < ema20) and (ema20 < ema50) and (c_now < l2) and (rvol >= 1.5) and (25 <= rsi <= 42)

            sl_dist = max(atr * 1.2, c_now * 0.005)
            if buy_cond:
                sig = "HIGH PROB BUY 🟢"
                score = min(100, int(75 + (rvol * 5)))
                sl = round(c_now - sl_dist, 2)
                tgt = round(c_now + (sl_dist * 2), 2)
            elif sell_cond:
                sig = "HIGH PROB SELL 🔴"
                score = min(100, int(75 + (rvol * 5)))
                sl = round(c_now + sl_dist, 2)
                tgt = round(c_now - (sl_dist * 2), 2)
            else:
                sig = "NO SETUP ⚪"
                score = 40
                sl = 0.0
                tgt = 0.0

            rows.append({
                "Symbol": sym,
                "Sector": C.SYMBOL_SECTOR.get(sym, "Other"),
                "Price": round(c_now, 2),
                "Change %": round(chg, 2),
                "RVOL": rvol,
                "RSI": round(rsi, 1),
                "Setup Score": score,
                "Signal": sig,
                "Stop Loss": sl,
                "Target (1:2)": tgt,
                "Chart": tv_url(sym),
                "BO_2D": "2D High BO" if c_now > h2 else ("2D Low BO" if c_now < l2 else "-"),
                "BO_10D": "10D High BO" if c_now > h10 else ("10D Low BO" if c_now < l10 else "-"),
                "BO_50D": "50D High BO" if c_now > h50 else ("50D Low BO" if c_now < l50 else "-"),
                "NR7": nr7,
                "Day_Pos": dpos
            })
        except Exception:
            continue
    return pd.DataFrame(rows)

mdf = load_market_data()

adv = int((mdf["Change %"] > 0).sum())
dec = int((mdf["Change %"] < 0).sum())
hp_buy = int((mdf["Signal"] == "HIGH PROB BUY 🟢").sum())
hp_sell = int((mdf["Signal"] == "HIGH PROB SELL 🔴").sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("🟢 Advancing Stocks", f"{adv}", f"{round(adv/len(mdf)*100)}% Bullish")
m2.metric("🔴 Declining Stocks", f"{dec}", f"-{round(dec/len(mdf)*100)}% Bearish")
m3.metric("🎯 High-Prob BUY", f"{hp_buy}", "4-Filter Confirmed")
m4.metric("🎯 High-Prob SELL", f"{hp_sell}", "4-Filter Confirmed")
st.divider()

if menu == "🎯 High-Probability Setups":
    st.subheader("🎯 High-Probability Trade Setups (Trend + 2D Breakout + Volume >1.5x + RSI Confirmed)")
    flt = st.radio("Filter Setups:", ["All Confirmed Setups", "Only BUY 🟢", "Only SELL 🔴"], horizontal=True)
    
    show_df = mdf[mdf["Signal"] != "NO SETUP ⚪"].copy()
    if flt == "Only BUY 🟢":
        show_df = show_df[show_df["Signal"] == "HIGH PROB BUY 🟢"]
    elif flt == "Only SELL 🔴":
        show_df = show_df[show_df["Signal"] == "HIGH PROB SELL 🔴"]
    show_df = show_df.sort_values("RVOL", ascending=False)

    if show_df.empty:
        st.info("અત્યારે ચારેય ફિલ્ટર (Trend + Breakout + Volume + RSI) પાસ કરે તેવો કોઈ સ્ટોક નથી. ખોટા ટ્રેડથી બચવા માટે અત્યારે રાહ જોવી (Wait) શ્રેષ્ઠ છે.")
    else:
        cols = ["Symbol", "Sector", "Signal", "Setup Score", "Price", "Change %", "RVOL", "RSI", "Stop Loss", "Target (1:2)", "Chart"]
        styled = show_df[cols].style.map(color_signal, subset=["Signal"]).map(color_chg, subset=["Change %"]).format({"Price": "{:.2f}", "Change %": "{:+.2f}%", "RVOL": "{:.2f}x", "RSI": "{:.1f}", "Stop Loss": "{:.2f}", "Target (1:2)": "{:.2f}"})
        st.dataframe(styled, column_config=col_cfg, use_container_width=True, hide_index=True, height=550)

elif menu == "🔥 Market Pulse (Gainers/Losers)":
    st.subheader("🔥 Market Pulse – Top Movers & High Volume Shockers")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🚀 Top Gainers")
        g_df = mdf.sort_values("Change %", ascending=False).head(15)[["Symbol", "Price", "Change %", "RVOL", "Signal", "Chart"]]
        st.dataframe(g_df.style.map(color_signal, subset=["Signal"]).map(color_chg, subset=["Change %"]).format({"Price": "{:.2f}", "Change %": "{:+.2f}%", "RVOL": "{:.2f}x"}), column_config=col_cfg, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("### 🔻 Top Losers")
        l_df = mdf.sort_values("Change %", ascending=True).head(15)[["Symbol", "Price", "Change %", "RVOL", "Signal", "Chart"]]
        st.dataframe(l_df.style.map(color_signal, subset=["Signal"]).map(color_chg, subset=["Change %"]).format({"Price": "{:.2f}", "Change %": "{:+.2f}%", "RVOL": "{:.2f}x"}), column_config=col_cfg, use_container_width=True, hide_index=True)

    st.markdown("### ⚡ High Power Stocks (Volume > 1.5x Average)")
    hp_df = mdf[mdf["RVOL"] >= 1.5].sort_values("RVOL", ascending=False)[["Symbol", "Sector", "Price", "Change %", "RVOL", "Signal", "Chart"]]
    st.dataframe(hp_df.style.map(color_signal, subset=["Signal"]).map(color_chg, subset=["Change %"]).format({"Price": "{:.2f}", "Change %": "{:+.2f}%", "RVOL": "{:.2f}x"}), column_config=col_cfg, use_container_width=True, hide_index=True)

elif menu == "📊 Sector Heatmap (Treemap)":
    st.subheader("📊 Sector Scope – Visual Market Heatmap")
    fig_tree = px.treemap(
        mdf, path=[px.Constant("NSE F&O Market"), "Sector", "Symbol"],
        values="RVOL", color="Change %",
        color_continuous_scale=["#8b0000", "#ff4b4b", "#262730", "#00cc66", "#006400"],
        color_continuous_midpoint=0,
        hover_data=["Price", "Change %", "Signal"]
    )
    fig_tree.update_layout(height=600, margin=dict(t=30, l=10, r=10, b=10))
    st.plotly_chart(fig_tree, use_container_width=True)

    sel = st.selectbox("🔍 Drill-down Sector:", sorted(mdf["Sector"].unique()))

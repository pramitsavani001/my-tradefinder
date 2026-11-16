import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
import pyotp
import plotly.express as px
from SmartApi import SmartConnect

# 1. Dark Mode & Sophisticated UI Setup
st.set_page_config(page_title="TradeFinder Pro Workspace", page_icon="📈", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0b0f19; color: #e2e8f0; }
    div[data-testid="stMetric"] {
        background-color: #131a2a;
        border: 1px solid #1e293b;
        padding: 12px 15px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: #131a2a; padding: 8px; border-radius: 10px; }
    .stTabs [data-baseweb="tab"] { color: #94a3b8; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #1d4ed8 !important; color: white !important; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)

# Load Secrets
api_key = st.secrets.get("API_KEY", "")
client_code = st.secrets.get("CLIENT_CODE", "")
mpin = st.secrets.get("MPIN", "")
totp_secret = st.secrets.get("TOTP_SECRET", "")

# Header & Top Controls
col_title, col_tf, col_rr, col_btn = st.columns([3, 1.2, 1.2, 1])
with col_title:
    st.markdown("## 💠 TradeFinder Pro Workspace")
with col_tf:
    timeframe = st.selectbox("Timeframe", ["5m", "15m", "1h"], index=1, label_visibility="collapsed")
with col_rr:
    risk_reward = st.selectbox("Risk:Reward", [1.5, 2.0, 2.5, 3.0], index=1, format_func=lambda x: f"R:R 1:{x}", label_visibility="collapsed")
with col_btn:
    if st.button("🔄 Sync Live", use_container_width=True):
        st.cache_data.clear()

# Stock Universe with Sectors & Angel One Tokens
stocks_info = {
    "RELIANCE.NS": ("RELIANCE-EQ", "2885", "Energy"),
    "ONGC.NS": ("ONGC-EQ", "2475", "Energy"),
    "NTPC.NS": ("NTPC-EQ", "11630", "Energy"),
    "POWERGRID.NS": ("POWERGRID-EQ", "14977", "Energy"),
    "TCS.NS": ("TCS-EQ", "11536", "IT"),
    "INFY.NS": ("INFY-EQ", "1594", "IT"),
    "WIPRO.NS": ("WIPRO-EQ", "3787", "IT"),
    "HCLTECH.NS": ("HCLTECH-EQ", "7229", "IT"),
    "HDFCBANK.NS": ("HDFCBANK-EQ", "1333", "Banking"),
    "ICICIBANK.NS": ("ICICIBANK-EQ", "4963", "Banking"),
    "SBIN.NS": ("SBIN-EQ", "3045", "Banking"),
    "AXISBANK.NS": ("AXISBANK-EQ", "5900", "Banking"),
    "KOTAKBANK.NS": ("KOTAKBANK-EQ", "1922", "Banking"),
    "BAJFINANCE.NS": ("BAJFINANCE-EQ", "317", "Finance"),
    "TATAMOTORS.NS": ("TATAMOTORS-EQ", "3456", "Auto"),
    "MARUTI.NS": ("MARUTI-EQ", "10999", "Auto"),
    "M&M.NS": ("M&M-EQ", "2031", "Auto"),
    "SUNPHARMA.NS": ("SUNPHARMA-EQ", "3351", "Pharma"),
    "CIPLA.NS": ("CIPLA-EQ", "694", "Pharma"),
    "TATASTEEL.NS": ("TATASTEEL-EQ", "3499", "Metal"),
    "HINDALCO.NS": ("HINDALCO-EQ", "1363", "Metal"),
    "ITC.NS": ("ITC-EQ", "1660", "FMCG"),
    "HINDUNILVR.NS": ("HINDUNILVR-EQ", "1394", "FMCG"),
    "LT.NS": ("LT-EQ", "11483", "Infra"),
    "ADANIENT.NS": ("ADANIENT-EQ", "25", "Infra"),
    "TITAN.NS": ("TITAN-EQ", "3506", "Consumer")
}

@st.cache_data(ttl=60)
def fetch_global_indices():
    indices = {
        "NIFTY 50": "^NSEI",
        "BANK NIFTY": "^NSEBANK",
        "INDIA VIX": "^INDIAVIX",
        "DAX (Germany)": "^GDAXI",
        "DOW JONES": "^DJI",
        "BTC/USD": "BTC-USD"
    }
    idx_data = {}
    for name, sym in indices.items():
        try:
            d = yf.download(sym, period="2d", interval="1d", progress=False)
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            if len(d) >= 2:
                prev = float(d['Close'].iloc[-2])
                curr = float(d['Close'].iloc[-1])
                chg = ((curr - prev) / prev) * 100
                idx_data[name] = (round(curr, 2), round(chg, 2))
        except:
            pass
    return idx_data

@st.cache_data(ttl=30)
def scan_all_stocks(tf):
    results = []
    smart_api = None
    api_status = "Yahoo Delay Feed 🟡"

    if api_key and client_code and mpin and totp_secret:
        try:
            smart_api = SmartConnect(api_key=api_key)
            totp = pyotp.TOTP(totp_secret).now()
            session = smart_api.generateSession(client_code, mpin, totp)
            if session['status']:
                api_status = "Angel One 0-Sec Live 🟢"
            else:
                smart_api = None
        except:
            smart_api = None

    for y_sym, (angel_sym, token, sector) in stocks_info.items():
        try:
            # Intraday Data
            df = yf.download(y_sym, period="5d", interval=tf, progress=False)
            if df.empty or len(df) < 25:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Daily Data (for 10-Day & 50-Day Breakouts + Day High/Low)
            ddf = yf.download(y_sym, period="60d", interval="1d", progress=False)
            if isinstance(ddf.columns, pd.MultiIndex):
                ddf.columns = ddf.columns.get_level_values(0)

            df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
            df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
            df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)

            prev_close = float(ddf['Close'].iloc[-2])
            curr_price = float(df['Close'].iloc[-1])
            day_high = float(ddf['High'].iloc[-1])
            day_low = float(ddf['Low'].iloc[-1])

            if smart_api:
                try:
                    ltp_res = smart_api.ltpData("NSE", angel_sym, token)
                    if ltp_res['status']:
                        curr_price = float(ltp_res['data']['ltp'])
                except:
                    pass

            change_pct = ((curr_price - prev_close) / prev_close) * 100
            
            # 10-Min / Last Candle Momentum Spike
            last_candle_open = float(df['Open'].iloc[-1])
            candle_spike_pct = ((curr_price - last_candle_open) / last_candle_open) * 100

            # Volume Boost (Current Vol vs 20-period Avg Vol)
            avg_vol = float(df['Volume'].tail(20).mean())
            curr_vol = float(df['Volume'].iloc[-1])
            vol_boost = round(curr_vol / avg_vol, 2) if avg_vol > 0 else 1.0

            # 10-Day & 50-Day High/Low
            high_10d = float(ddf['High'].iloc[-11:-1].max())
            high_50d = float(ddf['High'].iloc[-51:-1].max()) if len(ddf) >= 51 else high_10d

            ema_val = float(df['EMA_20'].iloc[-1])
            rsi_val = float(df['RSI'].iloc[-1])
            atr_val = float(df['ATR'].iloc[-1])

            # Signal Logic
            if curr_price > ema_val and 55 <= rsi_val <= 75 and change_pct > 0.4:
                signal = "🟢 BUY"
                sl = round(curr_price - (1.5 * atr_val), 2)
                target = round(curr_price + (1.5 * atr_val * risk_reward), 2)
            elif curr_price < ema_val and 25 <= rsi_val <= 45 and change_pct < -0.4:
                signal = "🔴 SELL"
                sl = round(curr_price + (1.5 * atr_val), 2)
                target = round(curr_price - (1.5 * atr_val * risk_reward), 2)
            else:
                signal = "⚪ WAIT"
                sl, target = 0.0, 0.0

            clean_name = y_sym.replace(".NS", "")
            tv_sym = clean_name.replace("&", "_")
            tv_url = f"https://tradingview.com{tv_sym}"

            results.append({
                "Stock": clean_name,
                "Sector": sector,
                "TV_Link": tv_url,
                "LTP (₹)": round(curr_price, 2),
                "Change (%)": round(change_pct, 2),
                "Spike (%)": round(candle_spike_pct, 2),
                "Vol Boost (x)": vol_boost,
                "RSI": round(rsi_val, 1),
                "Signal": signal,
                "Stop-Loss": sl if sl > 0 else "-",
                "Target": target if target > 0 else "-",
                "Near Day High": curr_price >= (day_high * 0.996),
                "Near Day Low": curr_price <= (day_low * 1.004),
                "BO_10D": curr_price > high_10d,
                "BO_50D": curr_price > high_50d
            })
        except:
            pass

    return pd.DataFrame(results), api_status

# 2. Global Markets Ticker Strip (Like TradeFinder Home)
indices_data = fetch_global_indices()
if indices_data:
    cols = st.columns(len(indices_data))
    for i, (name, (val, chg)) in enumerate(indices_data.items()):
        cols[i].metric(label=name, value=f"{val:,}", delta=f"{chg}%")

with st.spinner("Loading Live Institutional Scanners..."):
    df, status_msg = scan_all_stocks(timeframe)

st.caption(f"Feed Status: **{status_msg}** | Timeframe: **{timeframe}** | Click 'Open 📈' on any stock for full TradingView chart.")

col_cfg = {
    "TV_Link": st.column_config.LinkColumn("Chart", display_text="Open 📈")
}

# 3. Multi-Tab TradeFinder Architecture
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚡ Market Pulse (Gainers/Losers/Boost)",
    "🔥 Insider Strategy (10-Min Spike & LOM)",
    "📊 Sector Scope (Heatmap)",
    "📈 Swing Spectrum (10D & 50D Breakout)",
    "🕯️ Live TradingView Terminal"
])

if not df.empty:
    # TAB 1: MARKET PULSE
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🚀 Top 10 Gainers (Momentum)")
            gainers = df.sort_values(by="Change (%)", ascending=False).head(10)
            st.dataframe(gainers[["Stock", "TV_Link", "LTP (₹)", "Change (%)", "Signal", "Stop-Loss", "Target"]], column_config=col_cfg, use_container_width=True, hide_index=True)
        with c2:
            st.subheader("📉 Top 10 Losers (Breakdown)")
            losers = df.sort_values(by="Change (%)", ascending=True).head(10)
            st.dataframe(losers[["Stock", "TV_Link", "LTP (₹)", "Change (%)", "Signal", "Stop-Loss", "Target"]], column_config=col_cfg, use_container_width=True, hide_index=True)

        st.divider()

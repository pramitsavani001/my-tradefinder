import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import pyotp
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from SmartApi import SmartConnect

# 1. Page Config & Dark Theme
st.set_page_config(page_title="TradeFinder Pro Live", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0b0f19; color: #f8fafc; }
    div[data-testid="stMetric"] {
        background-color: #131a2a;
        border: 1px solid #1e293b;
        padding: 10px 14px;
        border-radius: 8px;
    }
    div[role="radiogroup"] {
        background-color: #131a2a;
        padding: 8px 12px;
        border-radius: 10px;
        border: 1px solid #1e293b;
        gap: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Load Secrets
api_key = st.secrets.get("API_KEY", "")
client_code = st.secrets.get("CLIENT_CODE", "")
mpin = st.secrets.get("MPIN", "")
totp_secret = st.secrets.get("TOTP_SECRET", "")

# Top Bar
c_title, c_tf, c_rr, c_btn = st.columns([3.5, 1, 1, 1])
with c_title:
    st.markdown("### 💠 TradeFinder Pro Workspace (Intraday Live)")
with c_tf:
    timeframe = st.selectbox("Timeframe", ["5m", "15m", "1h"], index=1, label_visibility="collapsed")
with c_rr:
    risk_reward = st.selectbox("R:R", [1.5, 2.0, 2.5, 3.0], index=1, format_func=lambda x: f"R:R 1:{x}", label_visibility="collapsed")
with c_btn:
    if st.button("🔄 Refresh Live", use_container_width=True):
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
        "DAX": "^GDAXI",
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

@st.cache_data(ttl=25)
def scan_all_stocks(tf):
    results = []
    charts_dict = {}
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

    tickers = list(stocks_info.keys())
    intraday_bulk = yf.download(tickers, period="5d", interval=tf, group_by='ticker', progress=False)
    daily_bulk = yf.download(tickers, period="55d", interval="1d", group_by='ticker', progress=False)

    for y_sym, (angel_sym, token, sector) in stocks_info.items():
        try:
            df = intraday_bulk[y_sym].dropna()
            ddf = daily_bulk[y_sym].dropna()
            if len(df) < 25 or len(ddf) < 5:
                continue

            df = df.copy()
            df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
            df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
            df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
            charts_dict[y_sym.replace(".NS", "")] = df

            prev_close = float(ddf['Close'].iloc[-2])
            curr_price = float(df['Close'].iloc[-1])
            day_high = float(ddf['High'].iloc[-1])
            day_low = float(ddf['Low'].iloc[-1])

            # Sync Exact Live OHLC & LTP from Angel One
            if smart_api:
                try:
                    ltp_res = smart_api.ltpData("NSE", angel_sym, token)
                    if ltp_res['status']:
                        d_live = ltp_res['data']
                        curr_price = float(d_live['ltp'])
                        if float(d_live.get('high', 0)) > 0:
                            day_high = float(d_live['high'])
                        if float(d_live.get('low', 0)) > 0:
                            day_low = float(d_live['low'])
                        if float(d_live.get('close', 0)) > 0:
                            prev_close = float(d_live['close'])
                except:
                    pass

            change_pct = ((curr_price - prev_close) / prev_close) * 100
            
            # Distance from Day High & Day Low (%)
            dist_high_pct = round(((day_high - curr_price) / day_high) * 100, 2) if day_high > 0 else 99
            dist_low_pct = round(((curr_price - day_low) / day_low) * 100, 2) if day_low > 0 else 99

            # Volume Boost
            avg_vol = float(df['Volume'].tail(20).mean())
            curr_vol = float(df['Volume'].iloc[-1])
            vol_boost = round(curr_vol / avg_vol, 2) if avg_vol > 0 else 1.0

            # 10-Day & 50-Day Highs
            high_10d = float(ddf['High'].iloc[-11:-1].max())
            high_50d = float(ddf['High'].iloc[-51:-1].max()) if len(ddf) >= 51 else high_10d

            ema_val = float(df['EMA_20'].iloc[-1])
            rsi_val = float(df['RSI'].iloc[-1])
            atr_val = float(df['ATR'].iloc[-1])

            # Clear Buy / Sell / SL / Target Logic
            if curr_price > ema_val and rsi_val >= 52 and change_pct > 0.3:
                signal = "🟢 BUY"
                sl = round(curr_price - (1.5 * atr_val), 2)
                target = round(curr_price + (1.5 * atr_val * risk_reward), 2)
            elif curr_price < ema_val and rsi_val <= 48 and change_pct < -0.3:
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
                "Day Low": round(day_low, 2),
                "Day High": round(day_high, 2),
                "Change (%)": round(change_pct, 2),
                "Vol Boost (x)": vol_boost,
                "RSI": round(rsi_val, 1),
                "Signal": signal,
                "Stop-Loss": sl if sl > 0 else "-",
                "Target": target if target > 0 else "-",
                "Dist_High_%": dist_high_pct,
                "Dist_Low_%": dist_low_pct,
                "BO_10D": curr_price >= (high_10d * 0.995),
                "BO_50D": curr_price >= (high_50d * 0.995)
            })
        except:
            pass

    return pd.DataFrame(results), charts_dict, api_status

# Global Indices Strip
indices_data = fetch_global_indices()
if indices_data:
    cols = st.columns(len(indices_data))
    for i, (name, (val, chg)) in enumerate(indices_data.items()):
        cols[i].metric(label=name, value=f"{val:,}", delta=f"{chg}%")

with st.spinner("Syncing Angel One Live OHLC & Institutional Scanners..."):
    df, charts_data, status_msg = scan_all_stocks(timeframe)

st.caption(f"Feed Status: **{status_msg}** | Timeframe: **{timeframe}** | Click **'Open 📈'** to launch TradingView.")

active_section = st.radio(
    "Navigation",
    [
        "⚡ Market Pulse",
        "🔥 Insider Strategy & Heatmap",
        "📊 Sector Scope",
        "📈 Swing Spectrum",
        "🕯️ Live Interactive Chart"
    ],
    horizontal=True,
    label_visibility="collapsed"
)

col_cfg = {
    "TV_Link": st.column_config.LinkColumn("Chart", display_text="Open 📈")
}

if not df.empty:
    # SECTION 1: MARKET PULSE
    if active_section == "⚡ Market Pulse":
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🚀 Top 10 Gainers (Momentum)")
            gainers = df.sort_values(by="Change (%)", ascending=False).head(10)
            st.dataframe(gainers[["Stock", "TV_Link", "LTP (₹)", "Change (%)", "Signal", "Stop-Loss", "Target"]], column_config=col_cfg, use_container_width=True, hide_index=True)
        with c2:

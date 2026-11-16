import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import ta
import pyotp
from SmartApi import SmartConnect

st.set_page_config(page_title="My TradeFinder Pro", layout="wide")
st.title("🚀 Personal TradeFinder Pro (Live Scanner & TradingView)")

# Auto-load credentials from Streamlit Secrets
api_key = st.secrets.get("API_KEY", "")
client_code = st.secrets.get("CLIENT_CODE", "")
mpin = st.secrets.get("MPIN", "")
totp_secret = st.secrets.get("TOTP_SECRET", "")

st.sidebar.header("⚙️ Scanner Settings")
timeframe = st.sidebar.selectbox("Scanner Timeframe", ["5m", "15m", "1h"], index=1)
risk_reward = st.sidebar.slider("Risk : Reward Ratio", 1.5, 4.0, 2.0, 0.5)

# Expanded 26 Top NSE Stocks List (Yahoo Symbol : (Angel Symbol, Token))
stock_map = {
    "RELIANCE.NS": ("RELIANCE-EQ", "2885"),
    "TCS.NS": ("TCS-EQ", "11536"),
    "HDFCBANK.NS": ("HDFCBANK-EQ", "1333"),
    "INFY.NS": ("INFY-EQ", "1594"),
    "ICICIBANK.NS": ("ICICIBANK-EQ", "4963"),
    "SBIN.NS": ("SBIN-EQ", "3045"),
    "BHARTIARTL.NS": ("BHARTIARTL-EQ", "10604"),
    "ITC.NS": ("ITC-EQ", "1660"),
    "LT.NS": ("LT-EQ", "11483"),
    "BAJFINANCE.NS": ("BAJFINANCE-EQ", "317"),
    "TATAMOTORS.NS": ("TATAMOTORS-EQ", "3456"),
    "SUNPHARMA.NS": ("SUNPHARMA-EQ", "3351"),
    "MARUTI.NS": ("MARUTI-EQ", "10999"),
    "AXISBANK.NS": ("AXISBANK-EQ", "5900"),
    "WIPRO.NS": ("WIPRO-EQ", "3787"),
    "ADANIENT.NS": ("ADANIENT-EQ", "25"),
    "TATASTEEL.NS": ("TATASTEEL-EQ", "3499"),
    "NTPC.NS": ("NTPC-EQ", "11630"),
    "POWERGRID.NS": ("POWERGRID-EQ", "14977"),
    "M&M.NS": ("M&M-EQ", "2031"),
    "KOTAKBANK.NS": ("KOTAKBANK-EQ", "1922"),
    "HCLTECH.NS": ("HCLTECH-EQ", "7229"),
    "TITAN.NS": ("TITAN-EQ", "3506"),
    "ULTRACEMCO.NS": ("ULTRACEMCO-EQ", "11532"),
    "ASIANPAINT.NS": ("ASIANPAINT-EQ", "236"),
    "HINDUNILVR.NS": ("HINDUNILVR-EQ", "1394")
}

@st.cache_data(ttl=30)
def get_market_data(tf):
    results = []
    smart_api = None

    if api_key and client_code and mpin and totp_secret:
        try:
            smart_api = SmartConnect(api_key=api_key)
            totp = pyotp.TOTP(totp_secret).now()
            session = smart_api.generateSession(client_code, mpin, totp)
            if session['status']:
                st.sidebar.success("Angel One Live Connected! 🟢")
            else:
                st.sidebar.warning("Check Angel One Credentials (Using Yahoo Data)")
                smart_api = None
        except:
            smart_api = None

    for y_symbol, (angel_sym, token) in stock_map.items():
        try:
            df = yf.download(y_symbol, period="5d", interval=tf, progress=False)
            if df.empty or len(df) < 25:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
            df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
            df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)

            daily_df = yf.download(y_symbol, period="2d", interval="1d", progress=False)
            if isinstance(daily_df.columns, pd.MultiIndex):
                daily_df.columns = daily_df.columns.get_level_values(0)

            prev_close = float(daily_df['Close'].iloc[-2])
            curr_price = float(df['Close'].iloc[-1])

            if smart_api:
                try:
                    ltp_data = smart_api.ltpData("NSE", angel_sym, token)
                    if ltp_data['status']:
                        curr_price = float(ltp_data['data']['ltp'])
                except:
                    pass

            change_pct = ((curr_price - prev_close) / prev_close) * 100
            ema_val = float(df['EMA_20'].iloc[-1])
            rsi_val = float(df['RSI'].iloc[-1])
            atr_val = float(df['ATR'].iloc[-1])

            if curr_price > ema_val and 55 <= rsi_val <= 75 and change_pct > 0.4:
                signal = "🟢 BUY"
                entry = curr_price
                sl = round(entry - (1.5 * atr_val), 2)
                target = round(entry + (1.5 * atr_val * risk_reward), 2)
            elif curr_price < ema_val and 25 <= rsi_val <= 45 and change_pct < -0.4:
                signal = "🔴 SELL"
                entry = curr_price
                sl = round(entry + (1.5 * atr_val), 2)
                target = round(entry - (1.5 * atr_val * risk_reward), 2)
            else:
                signal = "⚪ WAIT"
                entry, sl, target = curr_price, 0.0, 0.0

            clean_name = y_symbol.replace(".NS", "")
            # TradingView Direct Chart Link (Replace & with _ for M&M)
            tv_symbol = clean_name.replace("&", "_")
            tv_url = f"https://tradingview.com{tv_symbol}"

            results.append({
                "Stock": clean_name,
                "TV_Link": tv_url,
                "TV_Symbol": tv_symbol,
                "Live Price (₹)": round(curr_price, 2),
                "Change (%)": round(change_pct, 2),
                "RSI": round(rsi_val, 1),
                "Signal": signal,
                "Stop-Loss (₹)": sl if sl > 0 else "-",
                "Target (₹)": target if target > 0 else "-"
            })
        except:
            pass

    return pd.DataFrame(results)

if st.button("🔄 Refresh Live Market Data"):
    st.cache_data.clear()

with st.spinner("Scanning Top NSE Stocks..."):
    df_res = get_market_data(timeframe)

# Table column configuration for clickable TradingView links
col_config = {
    "TV_Link": st.column_config.LinkColumn(
        "TradingView",
        help="Click to open full chart in TradingView",
        display_text="Open Chart 📈"
    )
}

if not df_res.empty:
    # 1. Top 10 Gainers & Top 10 Losers
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🚀 Top 10 Gainers (Bullish)")
        gainers = df_res.sort_values(by="Change (%)", ascending=False).head(10)
        st.dataframe(
            gainers[["Stock", "TV_Link", "Live Price (₹)", "Change (%)", "Signal", "Stop-Loss (₹)", "Target (₹)"]],
            column_config=col_config,
            use_container_width=True,
            hide_index=True
        )
    with c2:
        st.subheader("📉 Top 10 Losers (Bearish)")
        losers = df_res.sort_values(by="Change (%)", ascending=True).head(10)
        st.dataframe(
            losers[["Stock", "TV_Link", "Live Price (₹)", "Change (%)", "Signal", "Stop-Loss (₹)", "Target (₹)"]],
            column_config=col_config,
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # 2. Embedded Official TradingView Chart Widget
    st.subheader("🕯️ Live TradingView Chart (With 20 EMA & RSI)")
    selected_stock = st.selectbox("Select Stock for Live TradingView Chart:", df_res["Stock"].tolist())
    tv_sym = selected_stock.replace("&", "_")

    # Timeframe mapping for TradingView widget
    tf_map = {"5m": "5", "15m": "15", "1h": "60"}
    tv_interval = tf_map.get(timeframe, "15")

    tv_widget_html = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://tradingview.com"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "width": "100%",
        "height": 550,
        "symbol": "NSE:{tv_sym}",
        "interval": "{tv_interval}",
        "timezone": "Asia/Kolkata",
        "theme": "dark",
        "style": "1",
        "locale": "in",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "studies": [
          "MASimple@tv-basicstudies",
          "RSI@tv-basicstudies"
        ],
        "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """
    components.html(tv_widget_html, height=560)

    st.divider()

    # 3. Complete Market Scanner Board
    st.subheader("📋 Complete NSE Scanner Board")
    st.dataframe(
        df_res[["Stock", "TV_Link", "Live Price (₹)", "Change (%)", "RSI", "Signal", "Stop-Loss (₹)", "Target (₹)"]],
        column_config=col_config,
        use_container_width=True,
        hide_index=True
    )

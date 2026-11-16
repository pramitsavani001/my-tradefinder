import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import pyotp
import plotly.graph_objects as go
from SmartApi import SmartConnect

st.set_page_config(page_title="My TradeFinder", layout="wide")
st.title("🚀 મારું પર્સનલ TradeFinder (Auto-Connected)")

# Secrets માંથી ઓટોમેટિક વિગતો લેવી
api_key = st.secrets.get("API_KEY", "")
client_code = st.secrets.get("CLIENT_CODE", "")
mpin = st.secrets.get("MPIN", "")
totp_secret = st.secrets.get("TOTP_SECRET", "")

st.sidebar.header("⚙️ ટ્રેડિંગ સેટિંગ્સ")
timeframe = st.sidebar.selectbox("ટાઈમફ્રેમ પસંદ કરો", ["5m", "15m", "1h"], index=1)
risk_reward = st.sidebar.slider("Risk : Reward રેશિયો", 1.5, 4.0, 2.0, 0.5)

stock_map = {
    "RELIANCE.NS": ("RELIANCE-EQ", "2885"),
    "TCS.NS": ("TCS-EQ", "11536"),
    "HDFCBANK.NS": ("HDFCBANK-EQ", "1333"),
    "INFY.NS": ("INFY-EQ", "1594"),
    "ICICIBANK.NS": ("ICICIBANK-EQ", "4963"),
    "SBIN.NS": ("SBIN-EQ", "3045"),
    "TATAMOTORS.NS": ("TATAMOTORS-EQ", "3456"),
    "BAJFINANCE.NS": ("BAJFINANCE-EQ", "317"),
    "AXISBANK.NS": ("AXISBANK-EQ", "5900"),
    "ADANIENT.NS": ("ADANIENT-EQ", "25")
}

@st.cache_data(ttl=30)
def get_market_data(tf):
    results = []
    chart_data_dict = {}
    smart_api = None

    if api_key and client_code and mpin and totp_secret:
        try:
            smart_api = SmartConnect(api_key=api_key)
            totp = pyotp.TOTP(totp_secret).now()
            session = smart_api.generateSession(client_code, mpin, totp)
            if session['status']:
                st.sidebar.success("Angel One Live Connected! 🟢")
            else:
                st.sidebar.warning("Angel One લોગિન ચેક કરો (Yahoo ડેટા ચાલુ છે)")
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
            chart_data_dict[y_symbol] = df

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

            results.append({
                "Stock": y_symbol.replace(".NS", ""),
                "Full_Symbol": y_symbol,
                "Live Price (₹)": round(curr_price, 2),
                "Change (%)": round(change_pct, 2),
                "RSI": round(rsi_val, 1),
                "Signal": signal,
                "Entry (₹)": round(entry, 2),
                "Stop-Loss (₹)": sl if sl > 0 else "-",
                "Target (₹)": target if target > 0 else "-"
            })
        except:
            pass

    return pd.DataFrame(results), chart_data_dict

if st.button("🔄 લાઈવ ડેટા રિફ્રેશ કરો"):
    st.cache_data.clear()

df_res, charts = get_market_data(timeframe)

if not df_res.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🚀 Top Gainers (Bullish Trend)")
        gainers = df_res.sort_values(by="Change (%)", ascending=False).head(5)
        st.dataframe(gainers[["Stock", "Live Price (₹)", "Change (%)", "Signal", "Stop-Loss (₹)", "Target (₹)"]], use_container_width=True, hide_index=True)
    with c2:
        st.subheader("📉 Top Losers (Bearish Trend)")
        losers = df_res.sort_values(by="Change (%)", ascending=True).head(5)
        st.dataframe(losers[["Stock", "Live Price (₹)", "Change (%)", "Signal", "Stop-Loss (₹)", "Target (₹)"]], use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🕯️ લાઈવ કેન્ડલસ્ટિક ચાર્ટ અને 20 EMA ટ્રેન્ડ લાઈન")
    selected_stock_name = st.selectbox("ચાર્ટ જોવા માટે સ્ટોક પસંદ કરો:", df_res["Stock"].tolist())
    full_sym = selected_stock_name + ".NS"

    if full_sym in charts:
        cdf = charts[full_sym].tail(60)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=cdf.index, open=cdf['Open'], high=cdf['High'], low=cdf['Low'], close=cdf['Close'], name="Price"))
        fig.add_trace(go.Scatter(x=cdf.index, y=cdf['EMA_20'], mode='lines', line=dict(color='orange', width=2), name="20 EMA"))
        fig.update_layout(height=450, xaxis_rangeslider_visible=False, template="plotly_dark", title=f"{selected_stock_name} ({timeframe} Chart)")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📋 તમામ સ્ટોક્સનું સિગ્નલ, Stop-Loss અને Target બોર્ડ")
    st.dataframe(df_res.drop(columns=["Full_Symbol"]), use_container_width=True, hide_index=True)

import time
import requests
import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import pyotp
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from SmartApi import SmartConnect

st.set_page_config(page_title="TradeFinder Pro (All F&O)", page_icon="⚡", layout="wide")

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

api_key = st.secrets.get("API_KEY", "")
client_code = st.secrets.get("CLIENT_CODE", "")
mpin = st.secrets.get("MPIN", "")
totp_secret = st.secrets.get("TOTP_SECRET", "")

st.sidebar.header("💰 Risk & Capital Manager")
total_capital = st.sidebar.number_input("Total Capital (₹)", min_value=5000, value=30000, step=5000)
risk_per_trade_pct = st.sidebar.slider("Max Risk Per Trade (%)", 0.5, 5.0, 1.0, 0.5)
risk_reward = st.sidebar.selectbox("Risk : Reward Ratio", [1.5, 2.0, 2.5, 3.0], index=1)
timeframe = st.sidebar.selectbox("Scanner Timeframe", ["5m", "15m", "1h"], index=1)

st.sidebar.divider()
auto_live = st.sidebar.toggle("🔴 Auto-Live Mode (30s Refresh)", value=False)
st.sidebar.caption("Scanning ALL ~200+ NSE F&O (Option Chain) Stocks automatically.")

c_title, c_btn = st.columns()
with c_title:
    st.markdown("### 💠 TradeFinder Pro Live (All NSE Option Chain / F&O Stocks)")
with c_btn:
    if st.button("🔄 Sync All F&O", use_container_width=True):
        st.cache_data.clear()

SECTOR_MAP = {
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking", "AXISBANK": "Banking", "KOTAKBANK": "Banking",
    "INDUSINDBK": "Banking", "BANKBARODA": "Banking", "PNB": "Banking", "CANBK": "Banking", "FEDERALBNK": "Banking",
    "IDFCFIRSTB": "Banking", "AUBANK": "Banking", "BANDHANBNK": "Banking", "UNIONBANK": "Banking", "INDIANB": "Banking",
    "BAJFINANCE": "Finance", "BAJAJFINSV": "Finance", "CHOLAFIN": "Finance", "SHRIRAMFIN": "Finance", "MUTHOOTFIN": "Finance",
    "PFC": "Finance", "RECLTD": "Finance", "SBILIFE": "Finance", "HDFCLIFE": "Finance", "ICICIGI": "Finance",
    "JIOFIN": "Finance", "ABCAPITAL": "Finance", "LTF": "Finance", "MANAPPURAM": "Finance", "LICHSGFIN": "Finance",
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT", "LTIM": "IT", "PERSISTENT": "IT",
    "COFORGE": "IT", "MPHASIS": "IT", "LTTS": "IT", "KPITTECH": "IT", "TATAELXSI": "IT", "OFSS": "IT",
    "RELIANCE": "Energy", "ONGC": "Energy", "NTPC": "Energy", "POWERGRID": "Energy", "COALINDIA": "Energy",
    "TATAPOWER": "Energy", "ADANIGREEN": "Energy", "ADANIENSOL": "Energy", "BPCL": "Energy", "IOC": "Energy",
    "GAIL": "Energy", "NHPC": "Energy", "SJVN": "Energy", "CESC": "Energy", "PETRONET": "Energy", "IGL": "Energy",
    "TATAMOTORS": "Auto", "MARUTI": "Auto", "M&M": "Auto", "BAJAJ-AUTO": "Auto", "EICHERMOT": "Auto",
    "HEROMOTOCO": "Auto", "TVSMOTOR": "Auto", "ASHOKLEY": "Auto", "BHARATFORG": "Auto", "MOTHERSON": "Auto",
    "BALKRISIND": "Auto", "MRF": "Auto", "APOLLOTYRE": "Auto", "EXIDEIND": "Auto", "BOSCHLTD": "Auto",
    "SUNPHARMA": "Pharma", "CIPLA": "Pharma", "DRREDDY": "Pharma", "DIVISLAB": "Pharma", "APOLLOHOSP": "Pharma",
    "LUPIN": "Pharma", "AUROPHARMA": "Pharma", "TORNTPHARM": "Pharma", "ALKEM": "Pharma", "BIOCON": "Pharma",
    "ZYDUSLIFE": "Pharma", "GLENMARK": "Pharma", "LAURUSLABS": "Pharma", "MAXHEALTH": "Pharma", "FORTIS": "Pharma",
    "TATASTEEL": "Metal", "HINDALCO": "Metal", "JSWSTEEL": "Metal", "VEDL": "Metal", "JINDALSTEL": "Metal",
    "NMDC": "Metal", "SAIL": "Metal", "NATIONALUM": "Metal", "HINDCOPPER": "Metal", "HINDZINC": "Metal",
    "ITC": "FMCG", "HINDUNILVR": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG", "TATACONSUM": "FMCG",
    "GODREJCP": "FMCG", "DABUR": "FMCG", "MARICO": "FMCG", "COLPAL": "FMCG", "VBL": "FMCG", "UBL": "FMCG",
    "LT": "Infra & Defence", "ADANIENT": "Infra & Defence", "ADANIPORTS": "Infra & Defence", "HAL": "Infra & Defence",
    "BEL": "Infra & Defence", "BHEL": "Infra & Defence", "MAZDOCK": "Infra & Defence", "SIEMENS": "Infra & Defence",
    "ABB": "Infra & Defence", "CUMMINSIND": "Infra & Defence", "CGPOWER": "Infra & Defence", "GMRAIRPORT": "Infra & Defence",
    "DLF": "Realty", "GODREJPROP": "Realty", "OBEROIRLTY": "Realty", "LODHA": "Realty", "PRESTIGE": "Realty",
    "TITAN": "Consumer", "TRENT": "Consumer", "ZOMATO": "Consumer", "ETERNAL": "Consumer", "DIXON": "Consumer",
    "HAVELLS": "Consumer", "VOLTAS": "Consumer", "BLUESTARCO": "Consumer", "PAGEIND": "Consumer", "INDHOTEL": "Consumer",
    "IRCTC": "Consumer", "INDIGO": "Consumer", "NAUKRI": "Consumer", "DMART": "Consumer", "PAYTM": "Consumer",
    "ULTRACEMCO": "Cement & Chem", "GRASIM": "Cement & Chem", "AMBUJACEM": "Cement & Chem", "SHREECEM": "Cement & Chem",
    "ACC": "Cement & Chem", "DALBHARAT": "Cement & Chem", "PIDILITIND": "Cement & Chem", "SRF": "Cement & Chem",
    "PIIND": "Cement & Chem", "UPL": "Cement & Chem", "DEEPAKNTR": "Cement & Chem", "AARTIIND": "Cement & Chem",
    "BHARTIARTL": "Telecom", "INDUSTOWER": "Telecom", "IDEA": "Telecom"
}

@st.cache_data(ttl=86400)
def get_all_fno_universe():
    fno_dict = {}
    try:
        url = "https://angelbroking.com"
        res = requests.get(url, timeout=15).json()
        df_master = pd.DataFrame(res)
        nfo_stocks = df_master[(df_master['exch_seg'] == 'NFO') & (df_master['instrumenttype'] == 'FUTSTK')]['name'].unique()
        nse_eq = df_master[(df_master['exch_seg'] == 'NSE') & (df_master['symbol'].str.endswith('-EQ'))]
        nse_eq_filtered = nse_eq[nse_eq['name'].isin(nfo_stocks)]

        for _, row in nse_eq_filtered.iterrows():
            sym = row['name']
            fno_dict[sym] = {
                "angel_sym": row['symbol'],
                "token": str(row['token']),
                "y_sym": f"{sym}.NS",
                "sector": SECTOR_MAP.get(sym, "Midcap F&O")
            }
    except Exception:
        pass

    if not fno_dict:
        for sym, sec in SECTOR_MAP.items():
            fno_dict[sym] = {"angel_sym": f"{sym}-EQ", "token": "", "y_sym": f"{sym}.NS", "sector": sec}
    return fno_dict

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
        except Exception:
            pass
    return idx_data

@st.cache_data(ttl=30)
def scan_all_fno_stocks(tf, cap, risk_pct, rr):
    fno_universe = get_all_fno_universe()
    results = []
    charts_dict = {}
    smart_api = None
    api_status = "Yahoo Delay Feed 🟡"
    live_quotes = {}

    if api_key and client_code and mpin and totp_secret:
        try:
            smart_api = SmartConnect(api_key=api_key)
            totp = pyotp.TOTP(totp_secret).now()
            session = smart_api.generateSession(client_code, mpin, totp)
            if session['status']:
                api_status = f"Angel One 0-Sec Live ({len(fno_universe)} F&O Stocks) 🟢"
                all_tokens = [v["token"] for v in fno_universe.values() if v["token"]]
                for i in range(0, len(all_tokens), 50):
                    batch = all_tokens[i:i+50]
                    try:
                        q_res = smart_api.getMarketData("OHLC", {"NSE": batch})
                        if q_res and q_res.get("status") and "fetched" in q_res.get("data", {}):
                            for item in q_res["data"]["fetched"]:
                                live_quotes[str(item["symbolToken"])] = item
                    except Exception:
                        pass
            else:
                smart_api = None
        except Exception:
            smart_api = None

    tickers = [v["y_sym"] for v in fno_universe.values()]
    intraday_bulk = yf.download(tickers, period="5d", interval=tf, group_by='ticker', progress=False, threads=True)
    daily_bulk = yf.download(tickers, period="55d", interval="1d", group_by='ticker', progress=False, threads=True)

    max_risk_rs = (cap * risk_pct) / 100.0
    avail_cols = intraday_bulk.columns.get_level_values(0) if isinstance(intraday_bulk.columns, pd.MultiIndex) else []

    for clean_name, info in fno_universe.items():
        try:
            y_sym = info["y_sym"]
            token = info["token"]
            sector = info["sector"]

            if y_sym not in avail_cols:
                continue

            df = intraday_bulk[y_sym].dropna().copy()
            ddf = daily_bulk[y_sym].dropna().copy()
            if len(df) < 22 or len(ddf) < 5:
                continue

            df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
            df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
            df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)

            tp = (df['High'] + df['Low'] + df['Close']) / 3.0
            df['VWAP'] = (tp * df['Volume']).rolling(14).sum() / df['Volume'].rolling(14).sum()
            df['VWAP'] = df['VWAP'].fillna(df['EMA_20'])


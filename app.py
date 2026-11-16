import time, datetime as dt
import pandas as pd, pyotp, requests, streamlit as st
from SmartApi import SmartConnect
import config as C, strategy as S

st.set_page_config(page_title="TradeFlow Pro (All F&O Option-OI)", page_icon="⚡", layout="wide")
st.title("⚡ TradeFlow – All NSE F&O Option-OI Flow Scanner")

cap = st.sidebar.number_input("Capital (₹)", 5000, 5000000, C.CAPITAL, 5000)
risk = st.sidebar.slider("Risk per trade (%)", 0.25, 3.0, C.RISK_PCT, 0.25)
if st.sidebar.button("🔄 Capture Live OI Snapshot"): st.cache_data.clear()

@st.cache_resource
def angel_login():
    api = SmartConnect(api_key=C.API_KEY)
    r = api.generateSession(C.CLIENT_CODE, C.PIN, pyotp.TOTP(C.TOTP_SECRET).now())
    if not r.get("status"): raise RuntimeError(f"Login failed: {r.get('message')}")
    return api

@st.cache_data(ttl=86400)
def get_master():
    res = requests.get("https://angelbroking.com", timeout=45).json()
    return pd.DataFrame(res)

def fetch_quotes(api, exch, tokens, mode="FULL"):
    out = []
    for i in range(0, len(tokens), 50):
        time.sleep(0.45)
        r = api.getMarketData(mode, {exch: tokens[i:i+50]})
        if r and r.get("status"): out += r["data"].get("fetched", [])
    return out

def get_contracts(m, und, spot, n_strikes):
    typ = "OPTIDX" if und in C.INDEX_TOKENS else "OPTSTK"
    o = m[(m.exch_seg == "NFO") & (m.name == und) & (m.instrumenttype == typ)].copy()
    if o.empty: return o
    o["exp"] = pd.to_datetime(o.expiry, format="%d%b%Y")
    o = o[o.exp >= pd.Timestamp.today().normalize()]
    o = o[o.exp == o.exp.min()]; o["k"] = o.strike.astype(float) / 100
    strikes = sorted(o.k.unique())
    if not strikes: return o.iloc[0:0]
    atm = min(strikes, key=lambda x: abs(x - spot)); i = strikes.index(atm)
    o = o[o.k.isin(strikes[max(0, i - n_strikes): i + n_strikes + 1])]
    o["cp"] = o.symbol.str[-2:]
    return o[["token", "symbol", "k", "cp"]]

if "oi_history" not in st.session_state: st.session_state.oi_history = []

try:
    api = angel_login()
    m = get_master()
    all_fno_names = sorted(m[(m.exch_seg == "NFO") & (m.instrumenttype == "FUTSTK")].name.unique())
    eq_df = m[(m.exch_seg == "NSE") & (m.symbol.str.endswith("-EQ"))]
    eq_map = dict(zip(eq_df.name, eq_df.token.astype(str)))
    unders = list(C.INDEX_TOKENS) + all_fno_names
    sp_tokens = {u: (C.INDEX_TOKENS.get(u) or eq_map.get(u)) for u in unders if (C.INDEX_TOKENS.get(u) or eq_map.get(u))}

    with st.spinner(f"Scanning Live Option OI for ALL {len(all_fno_names)} F&O Stocks..."):
        q_spot = fetch_quotes(api, "NSE", list(sp_tokens.values()), "LTP")
        tok2u = {v: k for k, v in sp_tokens.items()}
        spot = {tok2u[str(x["symbolToken"])]: float(x["ltp"]) for x in q_spot if str(x["symbolToken"]) in tok2u}
        contracts = [get_contracts(m, u, p, 5 if u in C.INDEX_TOKENS else 1).assign(und=u) for u, p in spot.items()]
        allc = pd.concat([c for c in contracts if not c.empty])
        info = allc.set_index("token")
        q_oi = fetch_quotes(api, "NFO", list(allc.token.astype(str)), "FULL")
        snap = []
        for x in q_oi:
            tk = str(x["symbolToken"])
            if tk in info.index:
                r = info.loc[tk]
                snap.append({"und": r.und, "cp": r.cp, "oi": float(x.get("opnInterest", 0))})
        df_snap = pd.DataFrame(snap).groupby(["und", "cp"]).oi.sum().unstack(fill_value=0)
        st.session_state.oi_history.append((dt.datetime.now().strftime("%H:%M:%S"), df_snap))
        if len(st.session_state.oi_history) > 30: st.session_state.oi_history.pop(0)

    if len(st.session_state.oi_history) < 2:
        st.info(f"⏳ Snapshot #1 Captured for **{len(df_snap)} F&O Stocks & Indices**! Click **'🔄 Capture Live OI Snapshot'** once more (after 1 min in live market) to see live OI Change Flow.")
        st.dataframe(df_snap.rename(columns={"CE": "Total Call OI", "PE": "Total Put OI"}), use_container_width=True)
    else:
        t0, old_oi = st.session_state.oi_history[0]
        t1, new_oi = st.session_state.oi_history[-1]
        diff = (new_oi - old_oi).fillna(0)
        diff["score"] = [S.flow_score(r.get("CE", 0), r.get("PE", 0)) for _, r in diff.iterrows()]
        diff["bias"] = diff.score.map(S.bias_label)
        st.caption(f"Live OI Flow Window: **{t0} ➔ {t1}** | Total Scanned: **{len(diff)} F&O Underlyings**")

        mk = {u: diff.loc[u] for u in C.INDEX_TOKENS if u in diff.index}
        cols = st.columns(len(mk) or 1)
        for col, (u, r) in zip(cols, mk.items()): col.metric(f"{u} Option Flow", r.bias, f"Score: {r.score:+.2f}")

        st.subheader("📊 Sector Option-OI Flow")
        stk = diff[diff.index.isin(all_fno_names)].copy()
        stk["Sector"] = stk.index.map(lambda x: C.SYMBOL_SECTOR.get(x, "Midcap / Other F&O"))
        sec = stk.groupby("Sector").agg(Flow_Score=("score", "mean"), Stocks=("score", "size")).sort_values("Flow_Score", ascending=False)
        sec["Bias"] = sec.Flow_Score.map(S.bias_label)
        st.dataframe(sec.round(2), use_container_width=True)

        st.subheader(f"🔥 All {len(stk)} F&O Stocks Option-OI Flow (Strongest Movers First)")
        stk["TV_Chart"] = [f"https://tradingview.com:{s.replace('&','_').replace('-','_')}" for s in stk.index]
        st.dataframe(stk.sort_values("score", key=abs, ascending=False)[["Sector", "TV_Chart", "CE", "PE", "score", "Bias"]].rename(columns={"CE":"Δ Call OI","PE":"Δ Put OI","score":"Flow Score"}).round(2),
                     column_config={"TV_Chart": st.column_config.LinkColumn("Chart", display_text="📈 Open")}, use_container_width=True, height=550)
except Exception as e:
    st.error(f"Error: {e}")

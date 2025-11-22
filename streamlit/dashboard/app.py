# streamlit-dashboard/app.py — FIXED
import streamlit as st
from alpaca.trading.client import TradingClient
import time

st.set_page_config(page_title="Crypto Bot Dashboard", layout="wide")
if "client" not in st.session_state:
    st.session_state.client = TradingClient(st.secrets["API_KEY"], st.secrets["API_SECRET"], paper=True)

client = st.session_state.client
st.title("🚀 Crypto Trading Bot Dashboard")

try:
    acc = client.get_account()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Equity", f"${float(acc.portfolio_value):,.2f}")
    with col2:
        st.metric("Cash", f"${float(acc.cash):,.2f}")

    cols = st.columns(3)
    SYMBOLS = ["SHIB/USD", "PEPE/USD", "SOL/USD"]
    for i, sym in enumerate(SYMBOLS):
        with cols[i]:
            try:
                pos = client.get_position(sym)
                value = float(pos.market_value)
                pnl = float(pos.unrealized_plpc) * 100
                st.metric(sym.split("/")[0].upper(), f"${value:,.0f}", f"{pnl:+.2f}%")
            except:
                st.metric(sym.split("/")[0].upper(), "$0", "—")

    if st.button("🚨 EMERGENCY STOP ALL POSITIONS"):
        for sym in SYMBOLS:
            try:
                client.close_position(sym)
            except:
                pass
        st.success("All positions closed! Refresh page.")
        st.rerun()

    st.caption(f"Last updated: {time.strftime('%Y-%m-%d %H:%M UTC')}")
except Exception as e:
    st.error(f"Connection error: {e}. Check API keys in secrets.")
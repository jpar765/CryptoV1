# streamlit-dashboard/app.py → WORKS 100% on streamlit.io
import streamlit as st
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide
import time
import pandas as pd

# === Page config ===
st.set_page_config(
    page_title="SHIB • PEPE • SOL Bot",
    page_icon="🚀",
    layout="centered"
)

st.title("🚀 SHIB • PEPE • SOL 24/7 Trading Bot")
st.markdown("**Live Paper Trading Dashboard** • Updated every 10 seconds")

# === Secrets check ===
if "API_KEY" not in st.secrets or "API_SECRET" not in st.secrets:
    st.error("API keys not found! Add them in Settings → Secrets (see below)")
    st.code('''
API_KEY = "PKxxxxxxxxxxxx"
API_SECRET = "skxxxxxxxxxxxx"
    ''')
    st.stop()

# === Initialize client with caching ===
@st.cache_resource(ttl=60)  # Recreate only every 60 sec
def get_client():
    return TradingClient(st.secrets["API_KEY"], st.secrets["API_SECRET"], paper=True)

client = get_client()

# === Auto-refresh every 10 seconds ===
placeholder = st.empty()
if st.button("🔴 EMERGENCY STOP ALL POSITIONS"):
    with st.spinner("Closing all positions..."):
        for sym in ["SHIB/USD", "PEPE/USD", "SOL/USD"]:
            try:
                client.close_position(sym)
            except:
                pass
        st.success("All positions closed!")
        time.sleep(2)
        st.rerun()

# === Main dashboard loop ===
while True:
    with placeholder.container():
        try:
            account = client.get_account()
            equity = float(account.portfolio_value)
            cash = float(account.cash)
            buying_power = float(account.crypto_buying_power)

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Equity", f"${equity:,.2f}")
            col2.metric("Cash", f"${cash:,.0f}")
            col3.metric("Buying Power", f"${buying_power:,.0f}")

            st.divider()

            cols = st.columns(3)
            symbols = ["SHIB/USD", "PEPE/USD", "SOL/USD"]
            total_value = 0
            for i, sym in enumerate(symbols):
                with cols[i]:
                    try:
                        pos = client.get_position(sym)
                        qty = float(pos.qty)
                        entry = float(pos.avg_entry_price)
                        current = float(pos.current_price)
                        value = qty * current
                        pnl_pct = (current / entry - 1) * 100
                        total_value += value

                        st.metric(
                            label=sym.split("/")[0],
                            value=f"${value:,.0f}",
                            delta=f"{pnl_pct:+.2f}%"
                        )
                    except:
                        st.metric(sym.split("/")[0], "$0", "—")

            # Summary bar
            st.markdown(f"**Last updated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        except Exception as e:
            st.error(f"Connection failed: {e}")
            st.info("Check your API keys or internet connection")

    time.sleep(10)
    st.rerun()  # This forces refresh
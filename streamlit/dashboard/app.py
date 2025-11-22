# streamlit-dashboard/app.py → FIXED: No loops, stable refresh, health check passes
import streamlit as st
from alpaca.trading.client import TradingClient
import time

# === Page config ===
st.set_page_config(
    page_title="SHIB • PEPE • SOL Bot Dashboard",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 SHIB • PEPE • SOL 24/7 Trading Bot")
st.markdown("**Live Paper Trading Dashboard** • Click 'Refresh' for updates")

# === Secrets validation ===
if "API_KEY" not in st.secrets or st.secrets["API_KEY"] == "":
    st.error("❌ API keys missing! Go to Settings → Secrets and add:")
    st.code('''
API_KEY = "PKyourpaperkeyhere"
API_SECRET = "skyoursecretkeyhere"
    ''')
    st.stop()
else:
    st.sidebar.success("✅ API keys loaded")

# === Client with caching ===
@st.cache_resource(ttl=300)  # Cache for 5 minutes, auto-refreshes data
def get_client():
    return TradingClient(st.secrets["API_KEY"], st.secrets["API_SECRET"], paper=True)

client = get_client()

# === Emergency Stop Button ===
if st.button("🚨 EMERGENCY STOP ALL POSITIONS", type="primary"):
    with st.spinner("Closing all positions..."):
        symbols = ["SHIB/USD", "PEPE/USD", "SOL/USD"]
        closed = []
        for sym in symbols:
            try:
                client.close_position(sym)
                closed.append(sym)
            except Exception as e:
                st.warning(f"Failed to close {sym}: {e}")
        if closed:
            st.success(f"✅ Closed: {', '.join(closed)}")
    st.rerun()  # Refresh once after action

# === Main Dashboard ===
try:
    # Account summary
    account = client.get_account()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Equity", f"${float(account.portfolio_value):,.2f}")
    col2.metric("Cash", f"${float(account.cash):,.2f}")
    col3.metric("Buying Power", f"${float(account.crypto_buying_power):,.2f}")

    st.divider()

    # Positions
    symbols = ["SHIB/USD", "PEPE/USD", "SOL/USD"]
    cols = st.columns(3)
    total_pnl = 0.0
    for i, sym in enumerate(symbols):
        with cols[i]:
            try:
                pos = client.get_position(sym)
                value = float(pos.market_value)
                pnl_pct = float(pos.unrealized_plpc) * 100
                total_pnl += float(pos.unrealized_pl)
                st.metric(
                    label=sym.split("/")[0].upper(),
                    value=f"${value:,.0f}",
                    delta=f"{pnl_pct:+.1f}%"
                )
            except:
                st.metric(sym.split("/")[0].upper(), "$0", "—")

    # Total P&L
    st.metric("Total Unrealized P&L", f"${total_pnl:,.2f}")

    # Last update
    st.caption(f"**Last updated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

except Exception as e:
    st.error(f"❌ Connection error: {e}")
    st.info("💡 Tips: Check API keys, ensure paper trading is enabled, or try refreshing.")

# === Refresh Button ===
if st.button("🔄 Refresh Dashboard"):
    st.cache_data.clear()  # Clear cache for fresh data
    st.rerun()

# === Sidebar Tips ===
with st.sidebar:
    st.header("Quick Tips")
    st.markdown("""
    - Click **Refresh** every 1-5 min for live updates
    - Use **Emergency Stop** only if needed
    - Bot runs 24/7 on Render.com (check Telegram for alerts)
    - For issues: Verify Alpaca paper account has $1,000+ buying power
    """)
    st.markdown("[Alpaca Docs](https://alpaca.markets/docs/) | [Streamlit Help](https://docs.streamlit.io/)")
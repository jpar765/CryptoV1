# telegram-dashboard/dashboard.py — FIXED imports
import requests
import time
from alpaca.trading.client import TradingClient

# === SECRETS ===
API_KEY = "YOUR_ALPACA_KEY"
API_SECRET = "YOUR_ALPACA_SECRET"
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
SYMBOLS = ["SHIB/USD", "PEPE/USD", "SOL/USD"]

client = TradingClient(API_KEY, API_SECRET, paper=True)

def send_dashboard():
    acc = client.get_account()
    equity = float(acc.portfolio_value)
    positions = []
    for sym in SYMBOLS:
        try:
            pos = client.get_position(sym)
            pnl_pct = float(pos.unrealized_plpc) * 100
            value = float(pos.market_value)
            positions.append(f"• {sym.split('/')[0]}: <b>{pnl_pct:+.2f}%</b> (${value:,.0f})")
        except:
            pass
    pos_text = "\n".join(positions) if positions else "No open positions"
    text = f"<b>🤖 Crypto Bot Dashboard</b>\n\n<b>Equity:</b> ${equity:,.2f}\n\n<b>Positions:</b>\n{pos_text}\n\n<i>Updated: {time.strftime('%H:%M UTC')}</i>"
    keyboard = [[{"text": "🚨 EMERGENCY STOP ALL", "callback_data": "stop_bot"}]]
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard}
        }, timeout=10)
    except Exception as e:
        print(f"Dashboard send failed: {e}")

def handle_callbacks():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        response = requests.get(url, timeout=5).json()
        for update in response.get("result", []):
            if "callback_query" in update:
                data = update["callback_query"]["data"]
                if data == "stop_bot":
                    for sym in SYMBOLS:
                        try:
                            client.close_position(sym)
                        except:
                            pass
                    send_telegram("🚨 EMERGENCY STOP: All positions closed!")
                # Acknowledge callback
                ack_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
                requests.post(ack_url, json={"callback_query_id": update["callback_query"]["id"]})
    except:
        pass

while True:
    send_dashboard()
    handle_callbacks()
    time.sleep(300)  # Every 5 minutes
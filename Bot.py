import time
import requests

TOKEN = "8208194190:AAHYoazYcJJhuxog01IKwXIj-TJFDYu77EA"
CHAT_ID = "2129240893"
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def get_fng():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10).json()
        return res['data'][0]['value'], res['data'][0]['value_classification']
    except:
        return "50", "Normal"

def get_price(sym):
    try:
        res = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={sym}", timeout=10).json()
        return float(res["lastPrice"]), float(res["priceChangePercent"])
    except:
        return None, None

def report():
    val, cls = get_fng()
    msg = f"📊 *PIYASA RAPORU*\n😨 Korku: {val}/100 ({cls})\n--------------------\n"
    for s in COINS:
        p, c = get_price(s)
        name = s.replace("USDT", "")
        if p:
            emo = "🟢" if c >= 0 else "🔴"
            msg += f"🪙 *{name}:* ${p:,.2f} | %{c:.2f} {emo}\n"
    return msg

send_msg("🚀 Bot Aktif! `/fiyat` yazabilirsiniz.")
last_id = None

while True:
    try:
        res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id, "timeout": 2}, timeout=5).json()
        for u in res.get("result", []):
            last_id = u["update_id"] + 1
            if "message" in u and "text" in u["message"]:
                txt = u["message"]["text"].strip().lower()
                if txt in ["/fiyat", "fiyat"]:
                    send_msg(report())
                elif txt.startswith("/ekle "):
                    coin = txt.split(" ")[1].upper() + "USDT"
                    p, _ = get_price(coin)
                    if p and coin not in COINS:
                        COINS.append(coin)
                        send_msg(f"✅ {coin.replace('USDT','')} eklendi!")
                    else:
                        send_msg("❌ Eklenemedi veya zaten listede.")
                elif txt in ["/liste", "liste"]:
                    send_msg(f"📋 Liste: {', '.join([s.replace('USDT','') for s in COINS])}")
    except:
        pass
    time.sleep(2)


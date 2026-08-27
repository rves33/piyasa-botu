import time
import requests

TOKEN = "8208194190:AAHYoazYcJJhuxog01IKwXIj-TJFDYu77EA"
CHAT_ID = "2129240893"
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def get_fng():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", headers=HEADERS, timeout=10).json()
        return res['data'][0]['value'], res['data'][0]['value_classification']
    except:
        return "50", "Normal"

def get_bitget_ticker(symbol):
    url = f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={symbol}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        if res.get("code") == "00000" and res.get("data"):
            ticker = res["data"][0]
            price = float(ticker["lastPr"])
            change = float(ticker["change24h"]) * 100
            return price, change
    except Exception as e:
        print(f"Bitget Hatasi ({symbol}): {e}")
    return None, None

def report():
    val, cls = get_fng()
    msg = f"📊 *BİTGET PİYASA RAPORU*\n😨 *Korku:* {val}/100 ({cls})\n--------------------\n"
    for s in COINS:
        p, c = get_bitget_ticker(s)
        name = s.replace("USDT", "")
        if p is not None:
            emo = "🟢" if c >= 0 else "🔴"
            msg += f"🪙 *{name}:* ${p:,.2f} | %{c:.2f} {emo}\n"
        else:
            msg += f"🪙 *{name}:* Veri alinamadi\n"
    return msg

send_msg("🚀 *Bitget Botu Aktif!*\n`/fiyat` yazarak deneyebilirsiniz.")
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
                    p, _ = get_bitget_ticker(coin)
                    if p and coin not in COINS:
                        COINS.append(coin)
                        send_msg(f"✅ {coin.replace('USDT','')} eklendi!")
                    else:
                        send_msg("❌ Coin bulunamadi veya zaten listede.")
                elif txt in ["/liste", "liste"]:
                    send_msg(f"📋 Liste: {', '.join([s.replace('USDT','') for s in COINS])}")
    except:
        pass
    time.sleep(2)

import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = "8208194190:AAHYoazYcJJhuxog01IKwXIj-TJFDYu77EA"
CHAT_ID = "2129240893"

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

rsi_alert_status = {}
last_alert_check_time = 0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot Aktif ve Calisiyor!")
    def log_message(self, format, *args):
        return

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Mesaj gonderme hatasi: {e}")

def get_fng():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", headers=HEADERS, timeout=5).json()
        return int(res['data'][0]['value']), res['data'][0]['value_classification']
    except:
        return 50, "Normal"

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def get_bitget_data(symbol):
    price = None
    change = 0.0
    rsi = 50.0

    try:
        url_ticker = f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={symbol}"
        res = requests.get(url_ticker, headers=HEADERS, timeout=5).json()
        if res.get("code") == "00000" and res.get("data"):
            t = res["data"][0]
            price = float(t.get("lastPr", 0))
            change = float(t.get("change24h", 0)) * 100
    except:
        pass

    if price is None:
        return None, None, None

    try:
        url_candles = f"https://api.bitget.com/api/v2/spot/market/candles?symbol={symbol}&granularity=1H&limit=30"
        c_res = requests.get(url_candles, headers=HEADERS, timeout=5).json()
        if c_res.get("code") == "00000" and c_res.get("data"):
            candles = list(reversed(c_res["data"]))
            closes = [float(c[4]) for c in candles]
            if len(closes) > 5:
                rsi = calculate_rsi(closes)
    except:
        rsi = 50.0

    return price, change, rsi

def format_symbol(coin_input):
    coin = coin_input.strip().upper()
    if not coin.endswith("USDT"):
        coin += "USDT"
    return coin

def generate_signal(rsi, change):
    if rsi >= 70:
        return f"🔥 RSI: {rsi:.1f} (Aşırı Alım) -> 🔴 *Şişmiş Bölge, Short / Düzeltme Beklenebilir!*"
    elif rsi <= 30:
        return f"💎 RSI: {rsi:.1f} (Aşırı Satım) -> 🟢 *Dip Bölge, Long / Tepki Alımı İçin Uygun!*"
    elif change > 3:
        return f"📈 RSI: {rsi:.1f} (Yükseliş Trendi) -> 🟢 *Trend Yukarı, Long Denenebilir.*"
    elif change < -3:
        return f"📉 RSI: {rsi:.1f} (Düşüş Trendi) -> 🔴 *Trend Aşağı, Short / Dikkatli Olun.*"
    else:
        return f"⚖️ RSI: {rsi:.1f} (Nötr Bölge) -> 💤 *Yatay Seyir, Net Fırsat Bekleyin.*"

def single_coin_report(symbol):
    p, c, rsi = get_bitget_data(symbol)
    name = symbol.replace("USDT", "")
    if p is not None:
        emo = "🟢" if c >= 0 else "🔴"
        signal = generate_signal(rsi, c)
        msg = f"📊 *{name} ANALİZ RAPORU*\n" \
              f"💵 Fiyat: *${p:,.4f}* | Değişim (24s): *%{c:.2f}* {emo}\n" \
              f"💡 {signal}"
        return msg
    else:
        return f"❌ *{name}* Bitget borsasında bulunamadı."

def report():
    fng_val, cls = get_fng()
    msg = f"📊 *BİTGET PİYASA RAPORU*\n😨 *Korku/Açgözlülük:* {fng_val}/100 ({cls})\n━━━━━━━━━━━━━━━━━━━━\n"
    for s in COINS:
        p, c, rsi = get_bitget_data(s)
        name = s.replace("USDT", "")
        if p is not None:
            emo = "🟢" if c >= 0 else "🔴"
            signal = generate_signal(rsi, c)
            msg += f"🪙 *{name}:* ${p:,.2f} | %{c:.2f} {emo}\n" \
                   f"💡 {signal}\n\n"
        else:
            msg += f"🪙 *{name}:* Veri alınamadı\n\n"
    return msg

def check_rsi_alerts():
    global rsi_alert_status
    for s in COINS:
        p, _, rsi = get_bitget_data(s)
        if p is None or rsi is None:
            continue
        
        name = s.replace("USDT", "")
        current_status = rsi_alert_status.get(s, "NORMAL")

        if rsi >= 70 and current_status != "OVERBOUGHT":
            alert_text = f"🚨 *AŞIRI ALIM (SHORT) ALARMI!*\n🪙 *{name}* 1h RSI: *{rsi:.1f}*\n💵 Fiyat: ${p:,.2f}\n💡 Fiyat tepe/şişmiş bölgede, Short veya kar realizasyonu düşünülebilir."
            send_msg(alert_text)
            rsi_alert_status[s] = "OVERBOUGHT"
        elif rsi <= 30 and current_status != "OVERSOLD":
            alert_text = f"🚀 *AŞIRI SATIM (LONG) ALARMI!*\n🪙 *{name}* 1h RSI: *{rsi:.1f}*\n💵 Fiyat: ${p:,.2f}\n💡 Fiyat dip bölgede, Long denemesi için uygun olabilir."
            send_msg(alert_text)
            rsi_alert_status[s] = "OVERSOLD"
        elif 35 < rsi < 65:
            rsi_alert_status[s] = "NORMAL"

last_id = None
try:
    initial_updates = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=5).json()
    results = initial_updates.get("result", [])
    if results:
        last_id = results[-1]["update_id"] + 1
        requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id}, timeout=5)
except:
    pass

send_msg("🚀 *Bitget Botu Güncellendi ve Hazır!*")
check_rsi_alerts()

while True:
    now = time.time()
    if now - last_alert_check_time >= 60:
        check_rsi_alerts()
        last_alert_check_time = now

    try:
        res = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"offset": last_id, "timeout": 2},
            timeout=5
        ).json()

        for u in res.get("result", []):
            last_id = u["update_id"] + 1
            if "message" in u and "text" in u["message"]:
                txt = u["message"]["text"].strip()
                cmd_parts = txt.split()
                cmd = cmd_parts[0].lower() if len(cmd_parts) > 0 else ""

                if cmd in ["/fiyat", "fiyat"]:
                    if len(cmd_parts) == 1:
                        send_msg(report())
                    else:
                        sym = format_symbol(cmd_parts[1])
                        send_msg(single_coin_report(sym))

                elif cmd.startswith("/ekle"):
                    if len(cmd_parts) > 1:
                        symbol = format_symbol(cmd_parts[1])
                        p, _, _ = get_bitget_data(symbol)
                        if p is not None:
                            if symbol not in COINS:
                                COINS.append(symbol)
                                send_msg(f"✅ *{symbol.replace('USDT','')}* listeye eklendi! (Fiyat: ${p:,.4f})")
                            else:
                                send_msg(f"⚠️ Bu coin zaten listenizde var.")
                        else:
                            send_msg(f"❌ *{symbol}* Bitget'te bulunamadı.")

                elif cmd.startswith("/sil"):
                    if len(cmd_parts) > 1:
                        symbol = format_symbol(cmd_parts[1])
                        if symbol in COINS:
                            COINS.remove(symbol)
                            rsi_alert_status.pop(symbol, None)
                            send_msg(f"🗑️ *{symbol.replace('USDT','')}* listeden çıkarıldı.")
                        else:
                            send_msg(f"⚠️ Listenizde bulunmuyor.")

                elif cmd in ["/liste", "liste"]:
                    coin_names = [s.replace("USDT", "") for s in COINS]
                    send_msg(f"📋 *Takip Listesi:* {', '.join(coin_names)}")

    except Exception as e:
        print(f"Döngü hatası: {e}")

    time.sleep(2)

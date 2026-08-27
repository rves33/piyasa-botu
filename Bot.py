import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = "8208194190:AAHYoazYcJJhuxog01IKwXIj-TJFDYu77EA"
CHAT_ID = "2129240893"

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
last_alert_check_time = 0
alert_memory = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# Render port kontrolü için mini web sunucu
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
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
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Mesaj hatasi: {e}")

def get_fng():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", headers=HEADERS, timeout=5).json()
        return int(res['data'][0]['value']), res['data'][0]['value_classification']
    except:
        return 50, "Normal"

def get_bitget_ticker(symbol):
    try:
        url = f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={symbol}"
        res = requests.get(url, headers=HEADERS, timeout=6).json()
        if res.get("code") == "00000" and res.get("data"):
            t = res["data"][0]
            price = float(t.get("lastPr", 0))
            change = float(t.get("change24h", 0)) * 100
            high24 = float(t.get("high24h", price))
            low24 = float(t.get("low24h", price))
            return price, change, high24, low24
    except Exception as e:
        print(f"Ticker hatasi ({symbol}): {e}")
    return None, None, None, None

def format_symbol(coin_input):
    coin = coin_input.strip().upper()
    if not coin.endswith("USDT"):
        coin += "USDT"
    return coin

def generate_signal(change, price, high24, low24, fng_val):
    # Fiyatın 24s aralığındaki konumu (Stochastic Mantığı %0 - %100)
    rng = high24 - low24 if high24 > low24 else 1
    pos = ((price - low24) / rng) * 100

    if pos >= 85 or change >= 10:
        return f"🔥 Tepe Bölgesi (%{pos:.0f}) -> 🔴 *Aşırı Alım / Short & Düzeltme Riski Yüksek!*"
    elif pos <= 15 or change <= -10:
        return f"💎 Dip Bölgesi (%{pos:.0f}) -> 🟢 *Aşırı Satım / Tepki Alımı & Long İçin Fırsat!*"
    elif change > 3:
        return f"📈 Güçlü Alıcı (%{pos:.0f}) -> 🟢 *Trend Pozitif, Kademeli Long.*"
    elif change < -3:
        return f"📉 Güçlü Satıcı (%{pos:.0f}) -> 🔴 *Trend Negatif, Kademeli Short.*"
    else:
        return f"⚖️ Nötr Alan (%{pos:.0f}) -> 💤 *Yatay Seyir, Net Yön Beklenmeli.*"

def single_coin_report(symbol):
    p, c, h, l = get_bitget_ticker(symbol)
    name = symbol.replace("USDT", "")
    if p is not None:
        fng_val, _ = get_fng()
        emo = "🟢" if c >= 0 else "🔴"
        signal = generate_signal(c, p, h, l, fng_val)
        msg = f"📊 *{name} ANALİZ RAPORU*\n" \
              f"💵 Fiyat: *${p:,.4f}* | 24s Değişim: *%{c:.2f}* {emo}\n" \
              f"🔝 24s Zirve: ${h:,.4f} | 🔻 24s Dip: ${l:,.4f}\n" \
              f"💡 {signal}"
        return msg
    else:
        return f"❌ *{name}* Bitget borsasında bulunamadı."

def report():
    fng_val, cls = get_fng()
    msg = f"📊 *BİTGET PİYASA RAPORU*\n😨 *Korku/Açgözlülük:* {fng_val}/100 ({cls})\n━━━━━━━━━━━━━━━━━━━━\n"
    for s in COINS:
        p, c, h, l = get_bitget_ticker(s)
        name = s.replace("USDT", "")
        if p is not None:
            emo = "🟢" if c >= 0 else "🔴"
            signal = generate_signal(c, p, h, l, fng_val)
            msg += f"🪙 *{name}:* ${p:,.4f} | %{c:.2f} {emo}\n" \
                   f"💡 {signal}\n\n"
        else:
            msg += f"🪙 *{name}:* Veri alınamadı\n\n"
    return msg

def check_auto_alerts():
    global alert_memory
    fng_val, _ = get_fng()
    for s in COINS:
        p, c, h, l = get_bitget_ticker(s)
        if p is None:
            continue
        
        name = s.replace("USDT", "")
        rng = h - l if h > l else 1
        pos = ((p - l) / rng) * 100
        prev_state = alert_memory.get(s, "NORMAL")

        if pos >= 90 and prev_state != "HIGH":
            alert_text = f"🚨 *AŞIRI ALIM (SHORT) UYARISI!*\n🪙 *{name}* 24s tepe noktasına (%{pos:.0f}) ulaştı!\n💵 Fiyat: ${p:,.4f}\n💡 Fiyat çok şişti, Short / Kâr alma değerlendirilebilir."
            send_msg(alert_text)
            alert_memory[s] = "HIGH"
        elif pos <= 10 and prev_state != "LOW":
            alert_text = f"🚀 *AŞIRI SATIM (LONG) UYARISI!*\n🪙 *{name}* 24s dip noktasına (%{pos:.0f}) indi!\n💵 Fiyat: ${p:,.4f}\n💡 Dip seviyede, Long / Tepki alımı fırsatı olabilir."
            send_msg(alert_text)
            alert_memory[s] = "LOW"
        elif 30 < pos < 70:
            alert_memory[s] = "NORMAL"

# Eski bekleyen mesajları temizle
last_id = None
try:
    init_res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=5).json()
    items = init_res.get("result", [])
    if items:
        last_id = items[-1]["update_id"] + 1
        requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id}, timeout=5)
except:
    pass

send_msg("🚀 *Bitget Botu Aktif ve Hazır!*")

while True:
    now = time.time()
    if now - last_alert_check_time >= 60:
        check_auto_alerts()
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
                        p, _, _, _ = get_bitget_ticker(symbol)
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
                            alert_memory.pop(symbol, None)
                            send_msg(f"🗑️ *{symbol.replace('USDT','')}* listeden çıkarıldı.")
                        else:
                            send_msg(f"⚠️ Listenizde bulunmuyor.")

                elif cmd in ["/liste", "liste"]:
                    coin_names = [s.replace("USDT", "") for s in COINS]
                    send_msg(f"📋 *Takip Listesi:* {', '.join(coin_names)}")

    except Exception as e:
        print(f"Hata: {e}")

    time.sleep(2)

import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = "8208194190:AAHYoazYcJJhuxog01IKwXIj-TJFDYu77EA"
CHAT_ID = "2129240893"
RENDER_APP_URL = "https://piyasa-botu-1yi1.onrender.com"

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
last_alert_check_time = 0
last_keep_alive_time = 0
alert_memory = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"OK - Bot Aktif")
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

def get_bitget_candles_data(symbol, tf="1h"):
    gran_map = {"30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day"}
    gran = gran_map.get(tf.lower(), "1h")
    
    url = f"https://api.bitget.com/api/v2/spot/market/candles?symbol={symbol}&granularity={gran}&limit=30"
    try:
        res = requests.get(url, headers=HEADERS, timeout=6).json()
        if res.get("code") == "00000" and res.get("data") and len(res["data"]) > 1:
            candles = list(reversed(res["data"]))
            closes = [float(c[4]) for c in candles]
            current_price = closes[-1]
            prev_close = closes[-2]
            change = ((current_price - prev_close) / prev_close) * 100
            rsi = calculate_rsi(closes)
            return current_price, change, rsi
    except Exception as e:
        print(f"Mum verisi hatasi ({symbol}): {e}")

    # Mum verisi gelmezse ticker'dan son fiyatı çek
    try:
        url_t = f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={symbol}"
        res_t = requests.get(url_t, headers=HEADERS, timeout=5).json()
        if res_t.get("code") == "00000" and res_t.get("data"):
            t = res_t["data"][0]
            return float(t.get("lastPr", 0)), float(t.get("change24h", 0)) * 100, 50.0
    except:
        pass

    return None, None, None

def format_symbol(coin_input):
    coin = coin_input.strip().upper()
    if not coin.endswith("USDT"):
        coin += "USDT"
    return coin

def generate_signal(rsi, change):
    if rsi >= 70:
        return f"🔥 RSI: {rsi:.1f} (Aşırı Alım) -> 🔴 *Şişmiş Bölge, Düzeltme / Short Fırsatı!*"
    elif rsi <= 30:
        return f"💎 RSI: {rsi:.1f} (Aşırı Satım) -> 🟢 *Dip Bölge, Tepki Alımı / Long Fırsatı!*"
    elif rsi > 55 and change > 0:
        return f"📈 RSI: {rsi:.1f} (Pozitif Trend) -> 🟢 *Trend Yukarı, Long Denenebilir.*"
    elif rsi < 45 and change < 0:
        return f"📉 RSI: {rsi:.1f} (Negatif Trend) -> 🔴 *Trend Aşağı, Short / Riskli Bölge.*"
    else:
        return f"⚖️ RSI: {rsi:.1f} (Nötr Bölge) -> 💤 *Yatay Seyir, Fırsat Bekleyin.*"

def single_coin_report(symbol, tf="1h"):
    p, c, rsi = get_bitget_candles_data(symbol, tf)
    name = symbol.replace("USDT", "")
    tf_label = {"30m": "30 Dakikalık", "1h": "1 Saatlik", "4h": "4 Saatlik"}.get(tf, tf)
    
    if p is not None:
        emo = "🟢" if c >= 0 else "🔴"
        signal = generate_signal(rsi, c)
        msg = f"📊 *{name} ANALİZ RAPORU ({tf_label})*\n" \
              f"💵 Fiyat: *${p:,.4f}* | Değişim: *%{c:.2f}* {emo}\n" \
              f"💡 {signal}"
        return msg
    else:
        return f"❌ *{name}* Bitget borsasında bulunamadı."

def report(tf="1h"):
    fng_val, cls = get_fng()
    tf_label = {"30m": "30 Dakikalık", "1h": "1 Saatlik", "4h": "4 Saatlik"}.get(tf, tf)
    
    msg = f"📊 *BİTGET PİYASA RAPORU ({tf_label})*\n😨 *Korku/Açgözlülük:* {fng_val}/100 ({cls})\n━━━━━━━━━━━━━━━━━━━━\n"
    for s in COINS:
        p, c, rsi = get_bitget_candles_data(s, tf)
        name = s.replace("USDT", "")
        if p is not None:
            emo = "🟢" if c >= 0 else "🔴"
            signal = generate_signal(rsi, c)
            msg += f"🪙 *{name}:* ${p:,.4f} | %{c:.2f} {emo}\n" \
                   f"💡 {signal}\n\n"
        else:
            msg += f"🪙 *{name}:* Veri alınamadı\n\n"
    return msg

def check_auto_alerts():
    global alert_memory
    for s in COINS:
        p, c, rsi = get_bitget_candles_data(s, "1h")
        if p is None or rsi is None:
            continue
        
        name = s.replace("USDT", "")
        prev_state = alert_memory.get(s, "NORMAL")

        if rsi >= 70 and prev_state != "HIGH":
            alert_text = f"🚨 *AŞIRI ALIM (SHORT) UYARISI!*\n🪙 *{name}* 1h RSI: *{rsi:.1f}*\n💵 Fiyat: ${p:,.4f}\n💡 Fiyat şişmiş tepe bölgesinde, Short / Kâr alma değerlendirilebilir."
            send_msg(alert_text)
            alert_memory[s] = "HIGH"
        elif rsi <= 30 and prev_state != "LOW":
            alert_text = f"🚀 *AŞIRI SATIM (LONG) UYARISI!*\n🪙 *{name}* 1h RSI: *{rsi:.1f}*\n💵 Fiyat: ${p:,.4f}\n💡 Fiyat dip seviyede, Long / Tepki alımı fırsatı olabilir."
            send_msg(alert_text)
            alert_memory[s] = "LOW"
        elif 35 < rsi < 65:
            alert_memory[s] = "NORMAL"

last_id = None
try:
    init_res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=5).json()
    items = init_res.get("result", [])
    if items:
        last_id = items[-1]["update_id"] + 1
        requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id}, timeout=5)
except:
    pass

send_msg("🚀 *Bitget Botu Çoklu Zaman Dilimi Desteğiyle Güncellendi!*")

while True:
    now = time.time()

    if now - last_alert_check_time >= 60:
        check_auto_alerts()
        last_alert_check_time = now

    if now - last_keep_alive_time >= 480:
        try:
            requests.get(RENDER_APP_URL, timeout=5)
        except:
            pass
        last_keep_alive_time = now

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
                parts = txt.split()
                cmd = parts[0].lower() if len(parts) > 0 else ""

                if cmd in ["/fiyat", "fiyat"]:
                    # Argümanları ayrıştır
                    tf = "1h"
                    target_coin = None

                    for arg in parts[1:]:
                        arg_low = arg.lower()
                        if arg_low in ["30m", "1h", "4h"]:
                            tf = arg_low
                        else:
                            target_coin = format_symbol(arg)

                    if target_coin:
                        send_msg(single_coin_report(target_coin, tf))
                    else:
                        send_msg(report(tf))

                elif cmd.startswith("/ekle"):
                    if len(parts) > 1:
                        symbol = format_symbol(parts[1])
                        p, _, _ = get_bitget_candles_data(symbol, "1h")
                        if p is not None:
                            if symbol not in COINS:
                                COINS.append(symbol)
                                send_msg(f"✅ *{symbol.replace('USDT','')}* listeye eklendi! (Fiyat: ${p:,.4f})")
                            else:
                                send_msg(f"⚠️ Bu coin zaten listenizde var.")
                        else:
                            send_msg(f"❌ *{symbol}* Bitget'te bulunamadı.")

                elif cmd.startswith("/sil"):
                    if len(parts) > 1:
                        symbol = format_symbol(parts[1])
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
        print(f"Telegram dongu hatasi: {e}")

    time.sleep(2)

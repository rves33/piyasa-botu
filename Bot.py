import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = "8208194190:AAHYoazYcJJhuxog01IKwXIj-TJFDYu77EA"
CHAT_ID = "2129240893"

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
ALERT_THRESHOLD = 3.0

# RSI alarmlarının sürekli spam yapmaması için son durum takibi
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
    except:
        pass

def get_fng():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", headers=HEADERS, timeout=10).json()
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

def get_bitget_candles_analysis(symbol, granularity="1h"):
    url = f"https://api.bitget.com/api/v2/spot/market/candles?symbol={symbol}&granularity={granularity}&limit=30"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        if res.get("code") == "00000" and res.get("data"):
            candles = res["data"]
            candles = list(reversed(candles))
            closes = [float(c[4]) for c in candles]
            current_price = closes[-1]
            prev_close = closes[-2] if len(closes) > 1 else current_price
            change = ((current_price - prev_close) / prev_close) * 100
            rsi = calculate_rsi(closes)
            return current_price, change, rsi
    except Exception as e:
        print(f"Mum Hatasi ({symbol}): {e}")
    return None, None, None

def format_symbol(coin_input):
    coin = coin_input.strip().upper()
    if not coin.endswith("USDT"):
        coin += "USDT"
    return coin

def generate_signal(rsi, change):
    if rsi >= 70:
        return f"🔥 RSI: {rsi:.1f} (Aşırı Alım) -> 🔴 *Şişmiş Bölge, Short İçin Uygun / Düzeltme Beklenir!*"
    elif rsi <= 30:
        return f"💎 RSI: {rsi:.1f} (Aşırı Satım) -> 🟢 *Dip Bölge, Long İçin Uygun / Tepki Alımı!*"
    elif rsi > 55 and change > 0:
        return f"📈 RSI: {rsi:.1f} (Pozitif Momentum) -> 🟢 *Trend Yukarı, Kademeli Long.*"
    elif rsi < 45 and change < 0:
        return f"📉 RSI: {rsi:.1f} (Negatif Momentum) -> 🔴 *Trend Aşağı, Kademeli Short.*"
    else:
        return f"⚖️ RSI: {rsi:.1f} (Nötr Bölge) -> 💤 *Yatay Seyir, Net Yön Beklenmeli.*"

def report(granularity="1h"):
    fng_val, cls = get_fng()
    timeframe_labels = {"30m": "30 Dakikalık", "1h": "1 Saatlik", "4h": "4 Saatlik"}
    label = timeframe_labels.get(granularity, granularity)
    
    msg = f"📊 *BİTGET TEKNİK ANALİZ RAPORU ({label})*\n😨 *Korku:* {fng_val}/100 ({cls})\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    
    for s in COINS:
        p, c, rsi = get_bitget_candles_analysis(s, granularity)
        name = s.replace("USDT", "")
        if p is not None:
            emo = "🟢" if c >= 0 else "🔴"
            signal = generate_signal(rsi, c)
            msg += f"🪙 *{name}:* ${p:,.2f} | %{c:.2f} {emo}\n"
            msg += f"💡 {signal}\n\n"
        else:
            msg += f"🪙 *{name}:* Veri alınamadı\n\n"
            
    return msg

def check_rsi_and_moves():
    global rsi_alert_status
    for s in COINS:
        p, _, rsi = get_bitget_candles_analysis(s, "1h")
        if p is None or rsi is None:
            continue
        
        name = s.replace("USDT", "")
        current_status = rsi_alert_status.get(s, "NORMAL")

        # Aşırı Alım Alarmı (Short Bölgesi)
        if rsi >= 70 and current_status != "OVERBOUGHT":
            alert_text = (
                f"🚨 *AŞIRI ALIM (SHORT) ALARMI!*\n"
                f"🪙 *{name}* 1h RSI değeri *{rsi:.1f}* seviyesine ulaştı!\n"
                f"💵 Anlık Fiyat: ${p:,.2f}\n"
                f"💡 *Yorum:* Fiyat şişmiş durumda, short yönlü işlemler veya kar realizasyonu için değerlendirilebilir."
            )
            send_msg(alert_text)
            rsi_alert_status[s] = "OVERBOUGHT"

        # Aşırı Satım Alarmı (Long Bölgesi)
        elif rsi <= 30 and current_status != "OVERSOLD":
            alert_text = (
                f"🚀 *AŞIRI SATIM (LONG) ALARMI!*\n"
                f"🪙 *{name}* 1h RSI değeri *{rsi:.1f}* seviyesine düştü!\n"
                f"💵 Anlık Fiyat: ${p:,.2f}\n"
                f"💡 *Yorum:* Aşırı satım bölgesinde, dip seviyelerden long denemeleri veya kademeli alım için uygun olabilir."
            )
            send_msg(alert_text)
            rsi_alert_status[s] = "OVERSOLD"

        # Normal bölgeye döndüğünde durumu sıfırla ki tekrar alarm verebilsin
        elif 35 < rsi < 65:
            rsi_alert_status[s] = "NORMAL"

# Eski biriken mesajları temizle
last_id = None
try:
    initial_updates = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=5).json()
    results = initial_updates.get("result", [])
    if results:
        last_id = results[-1]["update_id"] + 1
        requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", params={"offset": last_id}, timeout=5)
except:
    pass

send_msg("🚀 *Otomatik RSI Long/Short Alarm Botu Aktif!*\n\nCoinler aşırı alım (RSI > 70) veya aşırı satım (RSI < 30) bölgelerine girdiğinde size otomatik haber verecektir.")
check_rsi_and_moves()

while True:
    now = time.time()
    if now - last_alert_check_time >= 60:
        check_rsi_and_moves()
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
                cmd_parts = txt.lower().split()
                cmd = cmd_parts[0] if len(cmd_parts) > 0 else ""

                if cmd in ["/fiyat", "fiyat"]:
                    tf = "1h"
                    if len(cmd_parts) > 1:
                        requested_tf = cmd_parts[1]
                        if requested_tf in ["30m", "1h", "4h"]:
                            tf = requested_tf
                    send_msg(report(granularity=tf))

                elif cmd.startswith("/ekle"):
                    if len(cmd_parts) > 1:
                        symbol = format_symbol(cmd_parts[1])
                        p, _, _ = get_bitget_candles_analysis(symbol, "1h")
                        if p is not None:
                            if symbol not in COINS:
                                COINS.append(symbol)
                                send_msg(f"✅ *{symbol.replace('USDT','')}* listeye eklendi! (Anlık: ${p:,.2f})")
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
        pass

    time.sleep(2)

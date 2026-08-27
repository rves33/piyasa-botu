import time
import requests

TOKEN = "8208194190:AAHYoazYcJJhuxog01IKwXIj-TJFDYu77EA"
CHAT_ID = "2129240893"

# Başlangıç coin listesi ve alarm eşiği (%)
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
ALERT_THRESHOLD = 3.0  # %3 ve üzeri ani hareketlerde alarm verir

# Fiyat geçmişi takibi (Sembol -> Son kaydedilen fiyat)
last_prices = {}
last_alert_check_time = 0

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
        print(f"Hata ({symbol}): {e}")
    return None, None

def format_symbol(coin_input):
    coin = coin_input.strip().upper()
    if not coin.endswith("USDT"):
        coin += "USDT"
    return coin

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

def check_sudden_moves():
    global last_prices
    for s in COINS:
        p, _ = get_bitget_ticker(s)
        if p is None:
            continue
        
        name = s.replace("USDT", "")
        if s in last_prices:
            old_p = last_prices[s]
            diff_percent = ((p - old_p) / old_p) * 100

            # Belirlenen eşik üzerinde ani hareket varsa alarm gönder
            if diff_percent >= ALERT_THRESHOLD:
                alert_text = (
                    f"🚀 *ANİ YÜKSELİŞ ALARMI!*\n"
                    f"🪙 *{name}* aniden fırladı!\n"
                    f"📈 Değişim: *+%{diff_percent:.2f}*\n"
                    f"💵 Eski Fiyat: ${old_p:,.2f}\n"
                    f"💵 Yeni Fiyat: ${p:,.2f}"
                )
                send_msg(alert_text)
                last_prices[s] = p  # Yeni baz fiyatı güncelle
            elif diff_percent <= -ALERT_THRESHOLD:
                alert_text = (
                    f"🚨 *ANİ DÜŞÜŞ ALARMI!*\n"
                    f"🪙 *{name}* sert düştü!\n"
                    f"📉 Değişim: *-%{abs(diff_percent):.2f}*\n"
                    f"💵 Eski Fiyat: ${old_p:,.2f}\n"
                    f"💵 Yeni Fiyat: ${p:,.2f}"
                )
                send_msg(alert_text)
                last_prices[s] = p  # Yeni baz fiyatı güncelle
        else:
            # İlk okuma
            last_prices[s] = p

# Başlangıç mesajı ve ilk fiyat kaydı
send_msg("🚀 *Bitget Alarm & Piyasa Botu Güncellendi!*\n\nKomutlar:\n• `/fiyat` - Güncel rapor\n• `/ekle xrp` - Listeye coin ekler\n• `/sil xrp` - Listeden çıkarır\n• `/liste` - Takip listesi\n• `/alarm 3` - Alarm yüzdesini ayarlar")
check_sudden_moves()
last_id = None

while True:
    now = time.time()
    # Her 60 saniyede bir ani fiyat hareketlerini kontrol et
    if now - last_alert_check_time >= 60:
        check_sudden_moves()
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
                cmd = txt.lower()

                if cmd in ["/fiyat", "fiyat"]:
                    send_msg(report())

                elif cmd.startswith("/ekle "):
                    parts = txt.split(" ")
                    if len(parts) > 1:
                        symbol = format_symbol(parts[1])
                        p, _ = get_bitget_ticker(symbol)
                        if p is not None:
                            if symbol not in COINS:
                                COINS.append(symbol)
                                last_prices[symbol] = p
                                send_msg(f"✅ *{symbol.replace('USDT','')}* Bitget listesine eklendi! (Anlık: ${p:,.2f})")
                            else:
                                send_msg(f"⚠️ *{symbol.replace('USDT','')}* zaten takip listenizde var.")
                        else:
                            send_msg(f"❌ *{symbol}* Bitget borsasında bulunamadı.")

                elif cmd.startswith("/sil "):
                    parts = txt.split(" ")
                    if len(parts) > 1:
                        symbol = format_symbol(parts[1])
                        if symbol in COINS:
                            COINS.remove(symbol)
                            last_prices.pop(symbol, None)
                            send_msg(f"🗑️ *{symbol.replace('USDT','')}* takip listesinden çıkarıldı.")
                        else:
                            send_msg(f"⚠️ *{symbol.replace('USDT','')}* listenizde bulunmuyor.")

                elif cmd.startswith("/alarm "):
                    parts = txt.split(" ")
                    if len(parts) > 1:
                        try:
                            val = float(parts[1].replace("%", "").replace(",", "."))
                            ALERT_THRESHOLD = val
                            send_msg(f"🔔 Ani değişim alarm eşiği *%{ALERT_THRESHOLD}* olarak ayarlandı.")
                        except:
                            send_msg("❌ Geçersiz değer. Örnek: `/alarm 3` veya `/alarm 2.5`")

                elif cmd in ["/liste", "liste"]:
                    coin_names = [s.replace("USDT", "") for s in COINS]
                    send_msg(f"📋 *Takip Listesi:* {', '.join(coin_names)}\n🔔 *Alarm Eşiği:* %{ALERT_THRESHOLD}")

    except Exception as e:
        pass

    time.sleep(2)

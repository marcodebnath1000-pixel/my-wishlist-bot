import telebot
from telebot import types
import requests
from bs4 import BeautifulSoup
import time
import threading
import re
import json
import os

# --- CONFIGURATION ---
API_TOKEN = '8589426688:AAE77V_xJod-b1QQDKCFjAnkCbaC-fDdwEE'
DATA_FILE = 'watchlist.json'
COOKIES_FILE = 'cookies.json'

bot = telebot.TeleBot(API_TOKEN)

# --- DATA MANAGEMENT ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

users_watchlist = load_json(DATA_FILE)
user_cookies = load_json(COOKIES_FILE)
temp_data = {}

# --- STOCK CHECKER ---
def check_stock(url, chat_id):
    try:
        session = requests.Session()
        cookies = user_cookies.get(str(chat_id), {})
        
        # Ye headers Shein ko lagega ki aap real Mobile user ho
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/'
        }
        
        # Direct Request (No Proxy needed on Railway/Koyeb)
        response = session.get(url, headers=headers, cookies=cookies, timeout=20, allow_redirects=True)
        
        if response.status_code != 200:
            return False
            
        content = response.text.lower()
        
        # Advanced detection logic
        # Agar "Add to Bag" mil raha hai toh stock hai
        if "add to bag" in content or "add to cart" in content or "buy now" in content:
            # Re-check for Sold out text
            if "sold out" not in content and "out of stock" not in content:
                return True
        return False
    except:
        return False

# --- MONITORING LOOP ---
def monitor_loop():
    while True:
        try:
            global users_watchlist
            for chat_id, items in list(users_watchlist.items()):
                remaining = []
                for item in items:
                    print(f"Checking: {item['url']} (Size: {item['size']})")
                    if check_stock(item['url'], chat_id):
                        msg = f"✅ **STOCK MIL GAYA!**\n\n📦 Size: {item['size']}\n🔗 [LINK]({item['url']})"
                        bot.send_message(chat_id, msg, parse_mode="Markdown")
                    else:
                        remaining.append(item)
                users_watchlist[chat_id] = remaining
            
            save_json(DATA_FILE, users_watchlist)
            time.sleep(120) # 2 minute wait
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(30)

# --- BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('📋 View List', '🗑️ Clear List', '🍪 Set Cookies')
    bot.reply_to(message, "👋 **Shein Monitor Active!**\nLink bhejein stock check karne ke liye.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '🍪 Set Cookies')
def set_cookies(message):
    msg = bot.send_message(message.chat.id, "Paste your Shein cookies (Format: key=val; key2=val2):")
    bot.register_next_step_handler(msg, save_cookies)

def save_cookies(message):
    try:
        cookie_dict = {c.split('=')[0].strip(): c.split('=')[1].strip() for c in message.text.split(';') if '=' in c}
        user_cookies[str(message.chat.id)] = cookie_dict
        save_json(COOKIES_FILE, user_cookies)
        bot.send_message(message.chat.id, "✅ Cookies Saved!")
    except:
        bot.send_message(message.chat.id, "❌ Invalid Format.")

@bot.message_handler(func=lambda m: m.text == '📋 View List')
def view(message):
    items = users_watchlist.get(str(message.chat.id), [])
    if not items: bot.send_message(message.chat.id, "Watchlist empty.")
    else: bot.send_message(message.chat.id, f"Monitoring {len(items)} items.")

@bot.message_handler(func=lambda m: m.text == '🗑️ Clear List')
def clear(message):
    users_watchlist[str(message.chat.id)] = []
    save_json(DATA_FILE, users_watchlist)
    bot.reply_to(message, "List Cleared!")

@bot.message_handler(content_types=['text', 'photo'])
def handle_msg(message):
    text = message.text or message.caption
    url_match = re.search(r'(https?://[^\s]+)', text)
    if url_match:
        url = url_match.group(0)
        temp_data[message.chat.id] = url
        markup = types.InlineKeyboardMarkup()
        btns = [types.InlineKeyboardButton(s, callback_data=f"sz_{s}") for s in ["XS", "S", "M", "L", "XL", "XXL"]]
        markup.add(*btns)
        bot.reply_to(message, "Link detected! Choose Size:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith('sz_'))
def handle_sz(call):
    size = call.data.split('_')[1]
    cid = str(call.message.chat.id)
    if call.message.chat.id in temp_data:
        if cid not in users_watchlist: users_watchlist[cid] = []
        users_watchlist[cid].append({'url': temp_data[call.message.chat.id], 'size': size})
        save_json(DATA_FILE, users_watchlist)
        bot.edit_message_text(f"✅ Monitoring started for Size {size}!", call.message.chat.id, call.message.message_id)
        del temp_data[call.message.chat.id]

if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    bot.infinity_polling()

import os
import threading
import time
import datetime
import io
import requests  # <-- Hum ab direct Requests use karenge
from flask import Flask
import telebot
from telebot import types
from PIL import Image
import base64

# ================= 1. CONFIGURATION =================
raw_token = os.environ.get("BOT_TOKEN", "8514223652:AAH-1qD3aU0PKgLtMmJatXxqZWwz5YQtjyY")
BOT_TOKEN = raw_token.strip().replace("'", "").replace('"', "")

raw_gemini = os.environ.get("GEMINI_API_KEY", "8514223652:AAH-1qD3aU0PKgLtMmJatXxqZWwz5YQtjyY")
GEMINI_API_KEY = raw_gemini.strip().replace("'", "").replace('"', "")

QR_IMAGE_PATH = "business_qr.jpg" 

bot = telebot.TeleBot(BOT_TOKEN)

# ================= 2. DIRECT API CONNECTION (NO LIBRARY) =================
def get_medical_advice(user_query, image_bytes=None):
    if not GEMINI_API_KEY:
        return "⚠️ Error: API Key missing."

    # Hum seedha Google ke URL par request bhejenge (Library bypass)
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    doctor_prompt = """
    Act as Dr. Sneha, an Advanced AI Medical Consultant.
    Language: Hinglish (Hindi + English mix).
    
    Structure response:
    1. 🚑 **Turant Upay (Immediate Relief):**
    2. 💊 **Dawa (Medicine):** Suggest OTC medicines.
    3. 🚫 **Parhez (Precautions):**
    
    Note: End with 'Main AI hu. Asli Doctor se milen.'
    """

    full_prompt = f"{doctor_prompt}\n\nUser Query: {user_query}"

    # Payload (Message Packet) taiyar karna
    payload = {
        "contents": [{
            "parts": [{"text": full_prompt}]
        }]
    }

    # Agar Image hai, to use bhi packet me daalo
    if image_bytes:
        # Image ko text code (base64) me badalna padta hai direct bhejne ke liye
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        payload["contents"][0]["parts"].append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": img_b64
            }
        })

    try:
        # Request bhejo
        response = requests.post(api_url, json=payload)
        
        # Check karo ki Google ne kya jawab diya
        if response.status_code == 200:
            data = response.json()
            # Jawab nikalo
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"⚠️ Google API Error: {response.text}"
            
    except Exception as e:
        return f"⚠️ Network Error: {str(e)}"

# ================= 3. PLANS & HANDLERS =================
PLANS = {
    "49":  {"price": 49,  "days": 1,  "name": "Quick Consult"}, 
    "149": {"price": 149, "days": 15, "name": "15 Days Care"},
    "299": {"price": 299, "days": 30, "name": "Monthly Health"},
    "599": {"price": 599, "days": 90, "name": "Premium Care"}
}
users_db = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for plan_id, details in PLANS.items():
        btn_text = f"₹{details['price']} ({details['days']} Days)"
        buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"buy_{plan_id}"))
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, 
                     "🙏 **Namaste! Main Dr. Sneha hu.**\n(Direct API Mode ✅)\n\nApna plan chunein 👇", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_payment_click(call):
    try:
        plan_id = call.data.split("_")[1]
        plan = PLANS.get(plan_id)
        if not plan: return
        
        bot.answer_callback_query(call.id, "Processing...")
        caption = f"🏥 **Plan:** {plan['name']}\n💰 **Amount:** ₹{plan['price']}\n👇 **QR Scan karein aur Screenshot bhejein**"

        if os.path.exists(QR_IMAGE_PATH):
            with open(QR_IMAGE_PATH, 'rb') as photo:
                bot.send_photo(call.message.chat.id, photo, caption=caption, parse_mode="Markdown")
            users_db[call.message.chat.id] = {"status": "pending_payment", "plan_attempt": plan_id}
        else:
            bot.send_message(call.message.chat.id, "⚠️ Error: QR Image missing.")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Error: {e}")

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    uid = message.chat.id
    udata = users_db.get(uid, {})

    if udata.get("status") == "pending_payment":
        plan_id = udata["plan_attempt"]
        expiry = datetime.datetime.now() + datetime.timedelta(days=PLANS[plan_id]['days'])
        users_db[uid] = {"status": "active", "plan_id": plan_id, "expiry": expiry}
        bot.reply_to(message, f"✅ **Verified!** Plan activate ho gaya hai.\nAb apni pareshani batayein.")
        return

    # Medical Photo Analysis (Direct Mode)
    bot.send_chat_action(uid, 'typing')
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        # Seedha bytes bhejo function ko
        reply = get_medical_advice("", image_bytes=downloaded)
        bot.reply_to(message, reply, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Error analyzing image: {e}")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    reply = get_medical_advice(message.text)
    try:
        bot.reply_to(message, reply, parse_mode="Markdown")
    except:
        bot.reply_to(message, reply)

# ================= 4. SERVER =================
app = Flask(__name__)
@app.route('/')
def home(): return "Dr. Sneha Direct Mode Live"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling()

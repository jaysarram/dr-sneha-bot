import os
import threading
import time
import datetime
import io
from flask import Flask
import telebot
from telebot import types
from groq import Groq  # <-- Hum Groq use kar rahe hain
from PIL import Image

# ================= 1. CONFIGURATION =================
# Telegram Token
raw_token = os.environ.get("BOT_TOKEN", "g8514223652:AAH-1qD3aU0PKgLtMmJatXxqZWwz5YQtjyY")
BOT_TOKEN = raw_token.strip().replace("'", "").replace('"', "")

# Groq API Key (Yahan dhyan dein: Ye 'GROQ_API_KEY' hi dhundega)
raw_groq = os.environ.get("GROQ_API_KEY", "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")
GROQ_API_KEY = raw_groq.strip().replace("'", "").replace('"', "")

QR_IMAGE_PATH = "business_qr.jpg" 

bot = telebot.TeleBot(BOT_TOKEN)

# AI Client Setup
ai_client = None
if GROQ_API_KEY:
    try:
        ai_client = Groq(api_key=GROQ_API_KEY)
        print("Success: Connected to Groq AI")
    except Exception as e:
        print(f"Groq Connection Error: {e}")
else:
    print("Error: GROQ_API_KEY not found in environment variables.")

# ================= 2. MEDICAL LOGIC (Groq Llama 3.3) =================
def get_medical_advice(user_query):
    if not ai_client:
        return "⚠️ Technical Error: Groq API Key missing or invalid."

    doctor_prompt = """
    Act as Dr. Sneha, an expert AI Medical Consultant.
    Language: Hinglish (Hindi + English mix).
    
    Structure response in 3 parts:
    1. 🚑 **Turant Upay (Immediate Relief):**
    2. 💊 **Dawa (Medicine):** Suggest generic medicines.
    3. 🚫 **Parhez (Precautions):**
    
    Disclaimer: End with 'Note: I am an AI. Serious conditions me Doctor ko dikhayen.'
    """
    
    try:
        # ✅ NEW WORKING MODEL (Llama 3.3)
        chat_completion = ai_client.chat.completions.create(
            messages=[
                {"role": "system", "content": doctor_prompt},
                {"role": "user", "content": user_query}
            ],
            model="llama-3.3-70b-versatile", 
            temperature=0.7
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

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
                     "🙏 **Namaste! Main Dr. Sneha hu.**\n(AI Status: Active ✅)\n\nApna plan chunein 👇", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_payment_click(call):
    try:
        plan_id = call.data.split("_")[1]
        plan = PLANS.get(plan_id)
        if not plan: return

        bot.answer_callback_query(call.id, "Processing...")
        caption = f"🏥 **Plan:** {plan['name']}\n💰 **Amount:** ₹{plan['price']}\n👇 **Scan QR & Send Screenshot**"

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
        bot.reply_to(message, f"✅ **Verified!** Plan Active until {expiry.strftime('%d-%m-%Y')}.\nAb bimari batayein.")
        return

    # Groq Free Photo Analysis Support nahi karta
    bot.reply_to(message, "⚠️ Maafi chahti hu, main abhi photo dekhkar dawai nahi bata sakti. Kripya dawai ka naam ya bimari likhkar bhejein.")

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
def home(): return "Dr. Sneha (Groq Llama 3.3) is Live"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling()

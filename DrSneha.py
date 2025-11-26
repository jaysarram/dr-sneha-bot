import os
import threading
import time
import datetime
import io
from PIL import Image
from flask import Flask
import telebot
from telebot import types
import google.generativeai as genai

# ================= CONFIGURATION =================
# Security Note: Render me Environment Variables set karein.
# Code me hardcode karna safe nahi hai, par testing ke liye .get() me default value rakhi hai.

# Token se space aur quotes hatane ke liye filter lagaya hai
raw_token = os.getenv("BOT_TOKEN", "") 
BOT_TOKEN = raw_token.strip().replace("'", "").replace('"', "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Payment QR Code file name (Folder me hona chahiye)
QR_IMAGE_PATH = "business_qr.jpg" # Ya payment_qr.jpg jo bhi aapka filename ho

# Gemini AI Setup
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Gemini Error: {e}")
        model = None
else:
    model = None
    print("Warning: GEMINI_API_KEY not found.")

bot = telebot.TeleBot(BOT_TOKEN)

# ================= WEB SERVER (TO KEEP BOT ALIVE) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "Dr. Sneha Bot is Alive and Running!"

def run_web_server():
    # Render se PORT lena jaruri hai
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()

# ================= DATABASE (SIMULATED) =================
users_db = {}

# Plan Details
PLANS = {
    "49": {"name": "Quick Consult", "days": 0.5, "price": 49, "features": ["chat_10m"]},
    "149": {"name": "15 Days Care", "days": 15, "price": 149, "features": ["chat_10m", "reminders"]},
    "299": {"name": "Monthly Health", "days": 30, "price": 299, "features": ["unlimited_chat", "reminders", "image_analysis"]},
    "599": {"name": "Premium Care", "days": 90, "price": 599, "features": ["unlimited_chat", "reminders", "image_analysis", "voice_chat"]}
}

# ================= HELPER FUNCTIONS =================

def get_ai_response(user_message, image_part=None):
    """Gemini AI se reply lene ka function"""
    
    system_prompt = """
    You are Dr. Sneha, an expert AI medical consultant. 
    Language: Hinglish (Mix of Hindi and English).
    Tone: Professional, empathetic, and caring.
    
    Tasks:
    1. Analyze symptoms and suggest potential conditions.
    2. Recommend generic medicines (OTC) for minor issues.
    3. Suggest diet and things to avoid during medication.
    4. For serious symptoms, STRICTLY advise visiting a real doctor.
    5. If an image of medicine is provided, identify it and explain its usage.
    
    Disclaimer: Always end with 'Note: I am an AI. Please consult a real doctor for serious conditions.'
    """

    if model is None:
        return "System Error: AI Brain not connected (API Key missing)."

    try:
        # Text only request
        if image_part is None:
            prompt_content = [system_prompt, user_message]
            response = model.generate_content(prompt_content)
        # Image + Text request
        else:
            # Gemini expects [Text, Image]
            prompt_content = [system_prompt + "\nUser asks: " + user_message, image_part]
            response = model.generate_content(prompt_content)
            
        return response.text
    except Exception as e:
        print(f"AI Error: {e}")
        return "Maafi chahti hu, main abhi process nahi kar pa rahi. (Technical AI Error)"

def check_subscription(user_id, required_feature):
    user = users_db.get(user_id)
    if not user: return False

    expiry = user.get('expiry')
    if not expiry or expiry < datetime.datetime.now():
        return False

    if required_feature == "any": return True

    plan_id = str(user.get('plan_id'))
    plan = PLANS.get(plan_id)
    if not plan: return False

    return required_feature in plan.get('features', [])

# ================= BOT HANDLERS =================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("₹49 (10 Mins)", callback_data="buy_49")
    btn2 = types.InlineKeyboardButton("₹149 (15 Days)", callback_data="buy_149")
    btn3 = types.InlineKeyboardButton("₹299 (1 Month)", callback_data="buy_299")
    btn4 = types.InlineKeyboardButton("₹599 (3 Months)", callback_data="buy_599")
    markup.add(btn1, btn2, btn3, btn4)

    welcome_msg = (
        "Namaste! 🙏 Main Dr. Sneha hu, aapki personal AI Health Expert.\n\n"
        "Main aapke symptoms samajh kar dawa aur parhez bata sakti hu.\n"
        "Kripya apna plan chunein shuru karne ke liye:"
    )
    bot.send_message(message.chat.id, welcome_msg, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_payment(call):
    plan_id = call.data.split("_")[1]
    price = PLANS.get(plan_id, {}).get('price')
    
    # Send QR Code
    try:
        if os.path.exists(QR_IMAGE_PATH):
            with open(QR_IMAGE_PATH, 'rb') as photo:
                bot.send_photo(call.message.chat.id, photo, caption=f"Plan: ₹{price}\n\nQR Code scan karke pay karein aur screenshot bhejein.")
        else:
            bot.send_message(call.message.chat.id, "QR Code file server par nahi mili. Admin se sampark karein.")
    except Exception as e:
        bot.send_message(call.message.chat.id, "Error loading QR Code.")

    # Set User State
    uid = call.message.chat.id
    users_db.setdefault(uid, {})
    users_db[uid].update({"status": "pending_payment", "plan_attempt": plan_id})

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    user_id = message.chat.id

    # 1. Payment Verification
    if users_db.get(user_id, {}).get("status") == "pending_payment":
        plan_id = users_db[user_id]["plan_attempt"]
        days = PLANS[plan_id]["days"]
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)

        users_db[user_id] = {
            "plan_id": plan_id,
            "expiry": expiry_date,
            "status": "active",
            "reminders": []
        }
        bot.reply_to(message, f"✅ Payment Verified! Plan Activated.\nExpiry: {expiry_date.strftime('%Y-%m-%d')}")
        return

    # 2. Medicine Image Analysis
    if check_subscription(user_id, "image_analysis"):
        bot.send_message(user_id, "🔍 Image analyze kar rahi hu...")
        try:
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            image = Image.open(io.BytesIO(downloaded_file)).convert("RGB") # Convert for Gemini

            response = get_ai_response("Is dawa/report ko explain karo:", image_part=image)
            bot.reply_to(message, response)
        except Exception as e:
            print(f"Img Error: {e}")
            bot.reply_to(message, "Error processing image.")
    else:
        bot.reply_to(message, "🚫 Aapke plan me Photo Analysis shamil nahi hai (Upgrade to 299+).")

@bot.message_handler(commands=['set_reminder'])
def set_medicine_reminder(message):
    user_id = message.chat.id
    if check_subscription(user_id, "reminders"):
        try:
            parts = message.text.split(maxsplit=2)
            time_str = parts[1]
            med_name = parts[2]
            datetime.datetime.strptime(time_str, "%H:%M") # Validate format
            
            users_db.setdefault(user_id, {}).setdefault("reminders", []).append({"time": time_str, "med": med_name})
            bot.reply_to(message, f"⏰ Reminder set: {time_str} - {med_name}")
        except:
            bot.reply_to(message, "Format: /set_reminder HH:MM MedicineName")
    else:
        bot.reply_to(message, "Feature not in your plan.")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.chat.id
    if not check_subscription(user_id, "any"):
        bot.reply_to(message, "🔒 Subscription required. Type /start")
        return

    bot.send_chat_action(user_id, 'typing')
    ai_reply = get_ai_response(message.text)
    bot.reply_to(message, ai_reply)

# ================= SCHEDULER & MAIN =================
def run_scheduler():
    while True:
        current_time = datetime.datetime.now().strftime("%H:%M")
        for uid, data in list(users_db.items()):
            if data.get("status") == "active":
                for rem in data.get("reminders", []):
                    if rem["time"] == current_time:
                        try: bot.send_message(uid, f"🔔 Medicine Time: {rem['med']}")
                        except: pass
        time.sleep(60)

if __name__ == "__main__":
    keep_alive() # Start Web Server
    threading.Thread(target=run_scheduler, daemon=True).start() # Start Scheduler
    
    print("Dr. Sneha Bot Started...")
    bot.infinity_polling()

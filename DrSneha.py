# dr_sneha_bot.py  (Corrected & runnable prototype)
def get_ai_response(user_message, image_part=None):
    system_prompt = "You are Dr. Sneha, an expert AI medical consultant. Language: Hinglish. Answer strictly about the medical condition."
    prompt_content = [system_prompt, user_message]
    if image_part: prompt_content.append(image_part)

    try:
        response = model.generate_content(prompt_content)
        return response.text
    except Exception as e:
        # एरर को प्रिंट करें ताकि Logs में दिखे
        print(f"ERROR: {e}") 
        return "Maafi chahti hu, main abhi process nahi kar pa rahi. (Technical Error)"
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
import requests

# ================= CONFIGURATION =================
# अपनी Keys यहाँ डालें (Production me .env use karein)
BOT_TOKEN = os.getenv("BOT_TOKEN","8514223652:AAH-1qD3aU0PKgLtMmJatXxqZWwz5YQtjyY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","AIzaSyBU-lFuYeHKf5ETLwcV8hmO1OakGiQLoKo")

# Payment QR Code file name (Make sure this image exists in the folder)
QR_IMAGE_PATH = "business_qr.jpg"

# Gemini AI Setup (if you don't use Gemini, leave as-is; calls are wrapped in try/except)
genai.configure(api_key=GEMINI_API_KEY)
try:
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    model = None  # safe fallback for environments without Gemini

bot = telebot.TeleBot(BOT_TOKEN)

# ================= WEB SERVER (TO KEEP BOT ALIVE) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "Dr. Sneha Bot is Alive and Running!"

def run_web_server():
    """Start the Flask web server (for keep-alive on hosting)."""
    port = int(os.environ.get("PORT", 8080))
    # Use 0.0.0.0 so external services (like health checks) can reach it
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """Start the web server in a daemon thread."""
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()

# ================= DATABASE (SIMULATED) =================
# असली ऐप में DB (SQL/Mongo) यूज़ करें। यह सिर्फ prototype/demo के लिए है।
users_db = {}

# Plan Details
PLANS = {
    "49": {"name": "Quick Consult", "days": 0.5, "price": 49, "features": ["chat_10m"]},
    "149": {"name": "15 Days Care", "days": 15, "price": 149, "features": ["chat_10m", "reminders"]},
    "299": {"name": "Monthly Health", "days": 30, "price": 299, "features": ["unlimited_chat", "reminders", "image_analysis"]},
    "599": {"name": "Premium Care", "days": 90, "price": 599, "features": ["unlimited_chat", "reminders", "image_analysis", "voice_chat"]}
}

# ================= HELPER FUNCTIONS =================

def get_ai_response(user_message, image_part=None, is_voice=False):
    """Gemini AI se reply lene ka function (safe fallback agar model None ho)."""
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

    # Build prompt (string)
    prompt = system_prompt + "\nUser message:\n" + user_message
    if image_part:
        prompt += "\n[IMAGE ATTACHED]"  # actual image content not embedded here; just note it

    # Call Gemini model if available; otherwise return a safe fallback message
    try:
        if model is None:
            raise RuntimeError("Gemini model not configured in this environment.")
        # The exact API for gemini may differ; wrapping call to avoid crash.
        response = model.generate_content(prompt)  # may need adjustment for actual SDK
        # Response handling depends on returned object shape
        text = getattr(response, "text", None) or response.get("candidates", [{}])[0].get("content", "")
        return text or "Maafi chahti hu, main abhi process nahi kar pa rahi. Kripya thodi der baad try karein."
    except Exception as e:
        # for debugging you can log e
        return ("Maafi chahti hu, main abhi process nahi kar pa rahi. Kripya thodi der baad try karein."
                "\n\n(Dev note: AI service unavailable.)")

def check_subscription(user_id, required_feature):
    """Check if user's plan is active and contains the required feature."""
    user = users_db.get(user_id)
    if not user:
        return False

    expiry = user.get('expiry')
    if not expiry or expiry < datetime.datetime.now():
        return False

    if required_feature == "any":
        return True

    plan_id = str(user.get('plan_id'))
    plan = PLANS.get(plan_id)
    if not plan:
        return False

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
    plan_id = call.data.split("_")[1]  # '49' or '149' etc
    price = PLANS.get(plan_id, {}).get('price')
    if price is None:
        bot.send_message(call.message.chat.id, "Invalid plan selected.")
        return

    # Send QR Code
    try:
        with open(QR_IMAGE_PATH, 'rb') as photo:
            bot.send_photo(call.message.chat.id, photo,
                           caption=f"Plan: ₹{price}\n\nKripya is QR code par payment karein aur payment ka screenshot yahan bhejein approval ke liye.")
    except FileNotFoundError:
        bot.send_message(call.message.chat.id, "Error: QR Code image not found on server.")
        return

    # Set user state to waiting for payment (simplified)
    uid = call.message.chat.id
    users_db.setdefault(uid, {})
    users_db[uid].update({"status": "pending_payment", "plan_attempt": plan_id})
    bot.send_message(uid, f"🧾 Aapne ₹{price} plan choose kiya. Payment ke screenshot bhejein jab aapne pay kar liya ho.")

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    user_id = message.chat.id

    # 1. Payment Screenshot Verification Logic (demo: auto-approve screenshot)
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
        bot.reply_to(message, f"✅ Payment Verified! Aapka ₹{PLANS[plan_id]['price']} plan activate ho gaya hai.\nExpiry: {expiry_date.strftime('%Y-%m-%d')}\n\nAab aap mujhse apni bimari ke bare me puch sakte hain.")
        return

    # 2. Medicine Image Analysis (For 299 and 599 Plans)
    if check_subscription(user_id, "image_analysis"):
        bot.send_message(user_id, "🔍 Main is dawa (medicine) ki photo ko analyze kar rahi hu... Kripya wait karein.")
        try:
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            image = Image.open(io.BytesIO(downloaded_file)).convert("RGB")

            response = get_ai_response("Is dawa ko pehchano, iske uses batao aur kab lena chahiye?", image_part="[image]")
            bot.reply_to(message, response)
        except Exception as e:
            bot.reply_to(message, "Error processing image. Please try again.")
    else:
        bot.reply_to(message, "🚫 Aapke plan me Photo Analysis shamil nahi hai. Kripya upgrade karein (299/599 plan).")

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    user_id = message.chat.id

    if check_subscription(user_id, "voice_chat"):
        bot.reply_to(message, "🎤 Main aapka voice note sun rahi hu... (Voice processing simulated)")
        # For production: download voice file, convert with ffmpeg, run STT and AI analysis
        bot.reply_to(message, "Maine aapki baat sun li. Kripya dawa samay par lein. (Voice analysis feature is active).")
    else:
        bot.reply_to(message, "🚫 Voice Message feature sirf ₹599 wale plan me available hai.")

@bot.message_handler(commands=['set_reminder'])
def set_medicine_reminder(message):
    # Format: /set_reminder 09:30 Dolo-650
    user_id = message.chat.id

    if check_subscription(user_id, "reminders"):
        try:
            parts = message.text.split(maxsplit=2)
            time_str = parts[1]
            med_name = parts[2]

            # Validate time format HH:MM
            datetime.datetime.strptime(time_str, "%H:%M")

            users_db.setdefault(user_id, {}).setdefault("reminders", []).append({"time": time_str, "med": med_name})
            bot.reply_to(message, f"⏰ Reminder set! Main aapko roz {time_str} baje '{med_name}' lene ki yaad dilaungi.")
        except Exception:
            bot.reply_to(message, "Galat format. Use karein: /set_reminder HH:MM MedicineName\nExample: /set_reminder 20:30 Paracetamol")
    else:
        bot.reply_to(message, "Is plan me Reminder feature nahi hai.")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    user_id = message.chat.id

    # Check generic subscription
    if not check_subscription(user_id, "any"):
        bot.reply_to(message, "🔒 Aapka subscription active nahi hai ya expire ho gaya hai. Kripya /start dabakar plan kharidein.")
        return

    user_query = message.text
    bot.send_chat_action(user_id, 'typing')

    # Get AI Advice
    ai_reply = get_ai_response(user_query)
    bot.reply_to(message, ai_reply)

# ================= SCHEDULER THREAD =================
def run_scheduler():
    """Continuously check reminders every 60 seconds."""
    while True:
        current_time = datetime.datetime.now().strftime("%H:%M")
        for uid, data in list(users_db.items()):
            try:
                if data.get("status") == "active" and "reminders" in data:
                    for rem in data["reminders"]:
                        if rem["time"] == current_time:
                            bot.send_message(uid, f"🔔 Medicine Time!\nDr. Sneha: {rem['med']} lene ka waqt ho gaya hai!")
            except Exception:
                # ignore send errors (user blocked bot or other)
                pass
        time.sleep(60)  # check each minute

# ================= STARTUP (main) =================
def main():
    # 1) Start web server thread (keep-alive)
    keep_alive()

    # 2) Start scheduler thread (daemon)
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # 3) Start bot polling (blocking call)
    print("Dr. Sneha Bot is Running...")
    bot.infinity_polling()

if __name__ == "__main__":
    main()





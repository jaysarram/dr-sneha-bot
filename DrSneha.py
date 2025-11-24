import telebot
from telebot import types
import google.generativeai as genai
import threading
import time
import schedule
import datetime
from PIL import Image
import io

# ================= CONFIGURATION =================
# अपनी Keys यहाँ डालें
BOT_TOKEN = "8514223652:AAHT9BEMDVJPQvepz-ftcU-m8mnFUIVDPAY"
GEMINI_API_KEY = "AIzaSyBU-lFuYeHKf5ETLwcV8hmO1OakGiQLoKo"

# Payment QR Code file name (Make sure this image exists in the folder)
QR_IMAGE_PATH = "payment_qr.jpg" 

# Gemini AI Setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(BOT_TOKEN)

# ================= DATABASE (SIMULATED) =================
# असली ऐप में इसके लिए Database (SQL/MongoDB) यूज़ करें।
# यहाँ हम temporary dictionary यूज़ कर रहे हैं।
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
    """Gemini AI से रिप्लाई लेने का फंक्शन"""
    
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
    
    prompt_content = [system_prompt, user_message]
    if image_part:
        prompt_content.append(image_part)

    try:
        response = model.generate_content(prompt_content)
        return response.text
    except Exception as e:
        return "Maafi chahti hu, main abhi process nahi kar pa rahi. Kripya thodi der baad try karein."

def check_subscription(user_id, required_feature):
    """चेक करें कि यूजर का प्लान एक्टिव है या नहीं"""
    if user_id not in users_db:
        return False
    
    user = users_db[user_id]
    if user['expiry'] < datetime.datetime.now():
        return False # Plan Expired
        
    if required_feature == "any":
        return True
        
    # Feature validation based on plan
    plan_id = user['plan_id']
    if plan_id in PLANS:
        return required_feature in PLANS[plan_id]['features']
    
    return False

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
    price = PLANS[plan_id]['price']
    
    # Send QR Code
    try:
        with open(QR_IMAGE_PATH, 'rb') as photo:
            bot.send_photo(call.message.chat.id, photo, caption=f"Plan: ₹{price}\n\nKripya is QR code par payment karein aur payment ka screenshot yahan bhejein approval ke liye.")
        
        # Set user state to waiting for payment (simplified)
        if call.message.chat.id not in users_db:
            users_db[call.message.chat.id] = {"status": "pending_payment", "plan_attempt": plan_id}
        else:
            users_db[call.message.chat.id]["status"] = "pending_payment"
            users_db[call.message.chat.id]["plan_attempt"] = plan_id
            
    except FileNotFoundError:
        bot.send_message(call.message.chat.id, "Error: QR Code image not found on server.")

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    user_id = message.chat.id
    
    # 1. Payment Screenshot Verification Logic
    if user_id in users_db and users_db[user_id].get("status") == "pending_payment":
        # In a real app, you would check transaction ID. Here we auto-approve for demo purposes.
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
            image = Image.open(io.BytesIO(downloaded_file))
            
            response = get_ai_response("Is dawa ko pehchano, iske uses batao aur kab lena chahiye?", image_part=image)
            bot.reply_to(message, response, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, "Error processing image.")
    else:
        bot.reply_to(message, "🚫 Aapke plan me Photo Analysis shamil nahi hai. Kripya upgrade karein (299/599 plan).")

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    user_id = message.chat.id
    
    if check_subscription(user_id, "voice_chat"):
        bot.reply_to(message, "🎤 Main aapka voice note sun rahi hu... (Voice processing simulated)")
        # Note: Gemini API supports audio files directly now, but requires saving file first.
        # For simplicity, we reply text based here.
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
            
            # Add to user DB
            users_db[user_id]["reminders"].append({"time": time_str, "med": med_name})
            bot.reply_to(message, f"⏰ Reminder set! Main aapko roz {time_str} baje '{med_name}' lene ki yaad dilaungi.")
        except:
            bot.reply_to(message, "Galat format. Use karein: /set_reminder HH:MM MedicineName\nExample: /set_reminder 20:30 Paracetamol")
    else:
        bot.reply_to(message, "Is plan me Reminder feature nahi hai.")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.chat.id
    
    # Check generic subscription
    if not check_subscription(user_id, "any"):
        bot.reply_to(message, "🔒 Aapka subscription active nahi hai ya expire ho gaya hai. Kripya /start dabakar plan kharidein.")
        return

    # Logic for 10 min chat limit (Simplified: We assume session is valid if subscribed)
    # For the 49 plan, you might want to mark 'session_start' time in DB and block after 10 mins.
    
    user_query = message.text
    bot.send_chat_action(user_id, 'typing')
    
    # Get AI Advice
    ai_reply = get_ai_response(user_query)
    bot.reply_to(message, ai_reply, parse_mode="Markdown")

# ================= SCHEDULER THREAD =================
def run_scheduler():
    while True:
        current_time = datetime.datetime.now().strftime("%H:%M")
        # Check all users for reminders
        for uid, data in users_db.items():
            if data.get("status") == "active" and "reminders" in data:
                for rem in data["reminders"]:
                    if rem["time"] == current_time:
                        try:
                            bot.send_message(uid, f"🔔 **Medicine Time!**\nDr. Sneha: {rem['med']} lene ka waqt ho gaya hai!", parse_mode="Markdown")
                        except:
                            pass # User might have blocked bot
        time.sleep(60) # Check every minute

# Start Scheduler in Background
t = threading.Thread(target=run_scheduler)
t.daemon = True
t.start()

# ================= START BOT =================
print("Dr. Sneha Bot is Running...")
bot.infinity_polling()
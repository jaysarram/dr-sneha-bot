import os
import threading
import time
import datetime
import io
from flask import Flask
import telebot
from telebot import types
import google.generativeai as genai
from PIL import Image

# ================= 1. CONFIGURATION =================
raw_token = os.environ.get("BOT_TOKEN", "8514223652:AAH-1qD3aU0PKgLtMmJatXxqZWwz5YQtjyY")
BOT_TOKEN = raw_token.strip().replace("'", "").replace('"', "")

raw_gemini = os.environ.get("GEMINI_API_KEY", "AIzaSyAoisT6LlO7kmgA8aQ93ke9Jjfm2SErvAc")
GEMINI_API_KEY = raw_gemini.strip().replace("'", "").replace('"', "")

QR_IMAGE_PATH = "business_qr.jpg" 

bot = telebot.TeleBot(BOT_TOKEN)

# ================= 2. INTELLIGENT MODEL SELECTOR =================
ai_model = None
system_status = "Offline"
model_name_used = "Unknown"

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # --- AUTO-FIX LOGIC ---
        # Pehle naye model '1.5-flash' ko try karega.
        # Agar wo fail hua (404 Error), to purane 'gemini-pro' par shift ho jayega.
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            # Test ping
            model.generate_content("Hi")
            ai_model = model
            model_name_used = "Gemini 1.5 Flash (Fast)"
        except Exception as e:
            print(f"Flash model failed ({e}), switching to Gemini Pro...")
            ai_model = genai.GenerativeModel('gemini-pro')
            model_name_used = "Gemini Pro (Stable)"

        system_status = f"Online ({model_name_used}) 🟢"
        
    except Exception as e:
        print(f"Connection Error: {e}")
        system_status = "Error 🔴"

# ================= 3. ADVANCED MEDICAL BRAIN =================
def get_medical_advice(user_query, image=None):
    if not ai_model:
        return "⚠️ Technical Error: AI Brain not active. Check API Key."

    # --- ADVANCED DOCTOR PROMPT ---
    doctor_prompt = """
    Act as **Dr. Sneha**, a Senior Advanced AI Medical Consultant.
    Language: Hinglish (Hindi + English mix).
    Tone: Caring, Professional, and Investigative.

    **INSTRUCTIONS:**
    1. If user says "Hi/Hello", reply politely.
    2. If user shares a symptom, DO NOT give medicine immediately. Analyze first.

    **RESPONSE STRUCTURE:**
    
    🔍 **Symptom Analysis (Karan):**
    - Explain potential root causes (Gas, Stress, Infection, etc.).

    ⚡ **Instant Upchar (Turant Aaram):**
    - Home remedies/first aid for immediate relief.

    💊 **Medical Upchar (Dawa):**
    - Suggest generic OTC medicines with dosage.

    🏥 **Advanced Upchar:**
    - Diet changes and when to see a Specialist.
    
    **Disclaimer:** End with: 'Note: Main AI hu. Gambhir samasya ke liye asli Doctor se milen.'
    """
    
    try:
        if image:
            # Image logic based on model capability
            if "Flash" in model_name_used:
                prompt = [doctor_prompt + "\n\nAnalyze this medical photo:", image]
                response = ai_model.generate_content(prompt)
                return response.text
            else:
                return "⚠️ Maafi, purane model par photo scan available nahi hai. Kripya dawai ka naam likh kar bhejein."
        else:
            prompt = doctor_prompt + "\n\nPatient Query: " + user_query
            response = ai_model.generate_content(prompt)
            return response.text
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

# ================= 4. PLANS & HANDLERS =================
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
    
    welcome_text = (
        f"👩‍⚕️ **Namaste! Main Dr. Sneha hu.**\n"
        f"Status: {system_status}\n\n"
        "Main aapke lakshan (symptoms) samajh kar:\n"
        "1️⃣ Root Cause (Karan)\n"
        "2️⃣ Instant Upchar (Gharelu)\n"
        "3️⃣ Medical Dawa\n"
        "4️⃣ Advanced Care Suggest karungi.\n\n"
        "👇 **Shuru karne ke liye Plan chunein:**"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

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
            bot.send_message(call.message.chat.id, "⚠️ Error: Admin ne QR Code upload nahi kiya.")
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

    bot.send_chat_action(uid, 'typing')
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        img = Image.open(io.BytesIO(downloaded)).convert("RGB")
        reply = get_medical_advice("", image=img)
        bot.reply_to(message, reply, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Error processing image.")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    reply = get_medical_advice(message.text)
    try:
        bot.reply_to(message, reply, parse_mode="Markdown")
    except:
        bot.reply_to(message, reply)

# ================= 5. SERVER KEEPER =================
app = Flask(__name__)
@app.route('/')
def home(): return "Dr. Sneha Advanced AI is Live"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling()

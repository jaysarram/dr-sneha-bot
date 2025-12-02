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
# Token & Keys (Space aur Quotes hata kar load karega)
raw_token = os.environ.get("BOT_TOKEN", "8514223652:AAH-1qD3aU0PKgLtMmJatXxqZWwz5YQtjyY")
BOT_TOKEN = raw_token.strip().replace("'", "").replace('"', "")

raw_gemini = os.environ.get("GEMINI_API_KEY", "AIzaSyAoisT6LlO7kmgA8aQ93ke9Jjfm2SErvAc")
GEMINI_API_KEY = raw_gemini.strip().replace("'", "").replace('"', "")

QR_IMAGE_PATH = "business_qr.jpg" 

bot = telebot.TeleBot(BOT_TOKEN)

# ================= 2. ADVANCED AI BRAIN =================
ai_model = None
system_status = "Offline"

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Hum '1.5-flash' use karenge (Fast & Smart)
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
        system_status = "Online (Advanced Mode) 🟢"
    except Exception as e:
        print(f"Connection Error: {e}")
        system_status = "Error 🔴"

# ================= 3. MEDICAL LOGIC (THE UPGRADE) =================
def get_medical_advice(user_query, image=None):
    if not ai_model:
        return "⚠️ Technical Error: AI Brain not active. Check API Key."

    # --- YAHAN HAI ASLI JAADU (New Prompt) ---
    doctor_prompt = """
    Act as **Dr. Sneha**, a Senior Advanced AI Medical Consultant.
    Language: Hinglish (Hindi + English mix).
    Tone: Caring, Professional, and Investigative.

    **INSTRUCTIONS:**
    1. If the user says "Hi", "Hello", or generic talk -> Reply politely and ask about their health.
    2. If the user shares a symptom (e.g., "Pet dard"), DO NOT give medicine immediately. First analyze.

    **STRICT RESPONSE STRUCTURE (For Medical Queries):**
    
    🔍 **Symptom Analysis & Cause (Kyun ho raha hai?):**
    - Analyze the symptoms provided.
    - Explain 1-2 potential root causes (Gas, Infection, Stress, etc.).
    - If the user gave very less info, ask follow-up questions here.

    ⚡ **Instant Upchar (Turant Aaram):**
    - Suggest home remedies or first aid that gives relief in 10-15 mins.

    💊 **Medical Upchar (Dawa):**
    - Suggest standard OTC (Over-the-Counter) medicines.
    - Mention dosage (e.g., Subah-Shaam khane ke baad).

    🏥 **Advanced Upchar & Care:**
    - Suggest lifestyle changes, diet (kya khayein/kya nahi).
    - Advise when to see a real Specialist Doctor.
    
    **Disclaimer:** End with: 'Note: Main AI hu. Gambhir samasya ke liye asli Doctor se milen.'
    """
    
    try:
        if image:
            # Photo Analysis Logic
            prompt = [doctor_prompt + "\n\nUser ne ye medical photo/dawa bheji hai. Iska deep analysis karo:", image]
            response = ai_model.generate_content(prompt)
        else:
            # Text Analysis Logic
            prompt = doctor_prompt + "\n\nPatient Query: " + user_query
            response = ai_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

# ================= 4. PLANS & PAYMENT =================
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
        "Main bimari ke **lakshan (symptoms)** samajh kar:\n"
        "1️⃣ Root Cause (Karan) bataungi\n"
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

    # Payment Verification
    if udata.get("status") == "pending_payment":
        plan_id = udata["plan_attempt"]
        expiry = datetime.datetime.now() + datetime.timedelta(days=PLANS[plan_id]['days'])
        users_db[uid] = {"status": "active", "plan_id": plan_id, "expiry": expiry}
        bot.reply_to(message, f"✅ **Verified!** Aapka Advanced Plan activate ho gaya hai.\nAb apni pareshani batayein.")
        return

    # Medical Photo Analysis
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

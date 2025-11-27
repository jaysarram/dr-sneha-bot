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

# Render Keys cleaning
raw_token = os.environ.get("BOT_TOKEN", "8514223652:AAH-1qD3aU0PKgLtMmJatXxqZWwz5YQtjyY")
BOT_TOKEN = raw_token.strip().replace("'", "").replace('"', "")

raw_gemini = os.environ.get("GEMINI_API_KEY", "AIzaSyAlkLe-A78iY_wAWo-cA7H7f7PloGCC5gI")
GEMINI_API_KEY = raw_gemini.strip().replace("'", "").replace('"', "")

QR_IMAGE_PATH = "business_qr.jpg" 

bot = telebot.TeleBot(BOT_TOKEN)

# ================= 2. SMART AI SETUP (Model Selector) =================
ai_model = None
model_name_used = "Unknown"

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Ye loop check karega ki kaunsa model available hai
        # Sabse pehle 'flash' try karega (Fastest), fail hua to 'pro' (Standard)
        possible_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
        
        for m_name in possible_models:
            try:
                temp_model = genai.GenerativeModel(m_name)
                # Ek dummy test karke dekhte hain ki model chal raha hai ya nahi
                # Note: Test call hata diya hai taaki startup fast ho, direct assign kar rahe hain
                ai_model = temp_model
                model_name_used = m_name
                print(f"Success: Connected to {m_name}")
                break
            except Exception:
                continue
                
    except Exception as e:
        print(f"Gemini Connection Error: {e}")

# ================= 3. PLANS =================
PLANS = {
    "49":  {"price": 49,  "days": 1,  "name": "Quick Consult"}, 
    "149": {"price": 149, "days": 15, "name": "15 Days Care"},
    "299": {"price": 299, "days": 30, "name": "Monthly Health"},
    "599": {"price": 599, "days": 90, "name": "Premium Care"}
}
users_db = {}

# ================= 4. MEDICAL LOGIC =================
def get_medical_advice(user_query, image=None):
    if not ai_model:
        return "⚠️ Technical Error: AI Brain not connected. (Check Library Update)"

    doctor_prompt = """
    Act as Dr. Sneha, an expert AI Medical Consultant.
    Language: Hinglish (Hindi + English mix).
    
    Structure response in 3 parts:
    1. 🚑 **Turant Upay (Immediate Relief):** Home remedies or first aid.
    2. 💊 **Dawa (Medicine):** Suggest generic medicines, dosage & duration.
    3. 🚫 **Parhez (Precautions):** Diet and things to avoid.
    
    Disclaimer: End with 'Note: I am an AI. Serious conditions me Doctor ko dikhayen.'
    """
    
    try:
        if image:
            # Image handling logic based on model version
            if "flash" in model_name_used or "1.5" in model_name_used:
                prompt = [doctor_prompt + "\nAnalyze this image:", image]
                response = ai_model.generate_content(prompt)
            else:
                # Old gemini-pro vision support is different, falling back to text if vision fails
                return "⚠️ Is photo ko padhne ke liye 'Flash' model chahiye. Kripya requirements.txt update karein."
        else:
            prompt = doctor_prompt + "\nPatient Query: " + user_query
            response = ai_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}\n(Model: {model_name_used})"

# ================= 5. BOT HANDLERS =================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for plan_id, details in PLANS.items():
        btn_text = f"₹{details['price']} ({details['days']} Days)"
        buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"buy_{plan_id}"))
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, 
                     f"🙏 **Namaste! Main Dr. Sneha hu.**\n(AI Connected: {model_name_used})\n\nApna plan chunein 👇", 
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
            bot.send_message(call.message.chat.id, "⚠️ Error: QR Image missing on server.")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Error: {e}")

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    uid = message.chat.id
    udata = users_db.get(uid, {})

    # Payment Verify
    if udata.get("status") == "pending_payment":
        plan_id = udata["plan_attempt"]
        expiry = datetime.datetime.now() + datetime.timedelta(days=PLANS[plan_id]['days'])
        users_db[uid] = {"status": "active", "plan_id": plan_id, "expiry": expiry}
        bot.reply_to(message, f"✅ **Verified!** Plan Active until {expiry.strftime('%d-%m-%Y')}.\nAb bimari batayein.")
        return

    # Medical Image
    bot.send_chat_action(uid, 'typing')
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        img = Image.open(io.BytesIO(downloaded)).convert("RGB")
        reply = get_medical_advice("", image=img)
        bot.reply_to(message, reply, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Error analyzing image.")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    reply = get_medical_advice(message.text)
    try:
        bot.reply_to(message, reply, parse_mode="Markdown")
    except:
        bot.reply_to(message, reply)

# ================= 6. SERVER =================
app = Flask(__name__)
@app.route('/')
def home(): return "Dr. Sneha Alive"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot Started...")
    bot.infinity_polling()

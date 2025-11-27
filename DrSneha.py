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

# ================= 1. SETUP & KEYS =================

# Render Keys (Safe Cleaning)
raw_token = os.environ.get("BOT_TOKEN", "")
BOT_TOKEN = raw_token.strip().replace("'", "").replace('"', "")

raw_gemini = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEY = raw_gemini.strip().replace("'", "").replace('"', "")

# QR Code Image Name (GitHub par yahi naam hona chahiye)
QR_IMAGE_PATH = "business_qr.jpg" 

bot = telebot.TeleBot(BOT_TOKEN)

# AI Setup
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Gemini Error: {e}")

# ================= 2. PLANS CONFIGURATION =================
# Yahan aap plans aur validity change kar sakte hain
PLANS = {
    "49":  {"price": 49,  "days": 1,  "name": "Quick Consult"}, 
    "149": {"price": 149, "days": 15, "name": "15 Days Care"},
    "299": {"price": 299, "days": 30, "name": "Monthly Health"},
    "599": {"price": 599, "days": 90, "name": "Premium Care"}
}

# User Data (Temporary Memory)
users_db = {}

# ================= 3. AI MEDICAL LOGIC =================
def get_medical_advice(user_query, image=None):
    if not ai_model:
        return "⚠️ Technical Error: AI Brain not connected. (Check API Key)"

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
            prompt = [doctor_prompt + "\nAnalyze this medical image/medicine:", image]
            response = ai_model.generate_content(prompt)
        else:
            prompt = doctor_prompt + "\nPatient Query: " + user_query
            response = ai_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

# ================= 4. BOT HANDLERS =================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Dynamic Buttons create karna (Sare plans dikhenge)
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    
    for plan_id, details in PLANS.items():
        # Button text format: "₹49 (1 Day)"
        btn_text = f"₹{details['price']} ({details['days']} Days)"
        buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"buy_{plan_id}"))
    
    markup.add(*buttons)
    
    welcome_text = (
        "🙏 **Namaste! Main Dr. Sneha hu.**\n\n"
        "Main aapki bimari samajh kar dawa aur ilaj batati hu.\n"
        "Shuru karne ke liye apna plan chunein 👇"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# --- YE HAI BUTTON CLICK HANDLER (QR Code Wala) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_payment_click(call):
    try:
        # User ne kaunsa plan chuna?
        plan_id = call.data.split("_")[1]
        plan = PLANS.get(plan_id)
        
        if not plan:
            bot.answer_callback_query(call.id, "Plan not found!")
            return

        # 1. Message bhejo ki process shuru ho rha hai
        bot.answer_callback_query(call.id, "Processing Payment Request...")
        
        caption_text = (
            f"🏥 **Plan Selected:** {plan['name']}\n"
            f"💰 **Amount:** ₹{plan['price']}\n"
            f"📅 **Validity:** {plan['days']} Days\n\n"
            f"👇 **Niche diye gaye QR Code ko scan karke pay karein aur Screenshot yahan bhejein.**"
        )

        # 2. QR Code Image bhejo
        if os.path.exists(QR_IMAGE_PATH):
            with open(QR_IMAGE_PATH, 'rb') as photo:
                bot.send_photo(call.message.chat.id, photo, caption=caption_text, parse_mode="Markdown")
            
            # User ka status update karo taki screenshot verify ho sake
            uid = call.message.chat.id
            users_db[uid] = {"status": "pending_payment", "plan_attempt": plan_id}
            
        else:
            # Agar Image nahi mili to user ko batao
            bot.send_message(call.message.chat.id, 
                             f"⚠️ **Error:** QR Code image ('{QR_IMAGE_PATH}') server par nahi mili.\n"
                             f"Admin se kahen ki image upload karein.\n\n"
                             f"Plan Details: ₹{plan['price']} for {plan['days']} days.")
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Error: {str(e)}")

# --- SCREENSHOT & PHOTO HANDLER ---
@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    user_id = message.chat.id
    user_data = users_db.get(user_id, {})

    # Case 1: Payment Verification
    if user_data.get("status") == "pending_payment":
        plan_id = user_data["plan_attempt"]
        plan = PLANS[plan_id]
        
        # Payment Approve (Demo Logic)
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=plan['days'])
        users_db[user_id] = {
            "status": "active",
            "plan_id": plan_id,
            "expiry": expiry_date
        }
        
        success_msg = (
            f"✅ **Payment Verified!**\n\n"
            f"Plan: {plan['name']}\n"
            f"Expiry: {expiry_date.strftime('%d-%m-%Y')}\n\n"
            f"Ab aap apni bimari likhkar bhejein, main turant ilaj bataungi."
        )
        bot.reply_to(message, success_msg, parse_mode="Markdown")
        return

    # Case 2: Medicine/Disease Analysis (Agar active user hai)
    # (Abhi demo ke liye sabko allow kar rahe hain)
    bot.send_chat_action(user_id, 'typing')
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        img = Image.open(io.BytesIO(downloaded)).convert("RGB")
        
        reply = get_medical_advice("", image=img)
        bot.reply_to(message, reply, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Error analyzing image.")

# --- TEXT CHAT HANDLER ---
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    # Check Subscription logic yahan laga sakte hain
    # Abhi direct jawab dega
    bot.send_chat_action(message.chat.id, 'typing')
    reply = get_medical_advice(message.text)
    try:
        bot.reply_to(message, reply, parse_mode="Markdown")
    except:
        bot.reply_to(message, reply) # Markdown fail hone par plain text

# ================= 5. SERVER KEEPER =================
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot Started...")
    bot.infinity_polling()

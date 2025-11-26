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

# ================= 1. SETUP & CONFIGURATION =================

# Render se Keys nikalna (Quotes aur Spaces hata kar)
raw_token = os.environ.get("BOT_TOKEN", "8514223652:AAH-1qD3aU0PKgLtMmJatXxqZWwz5YQtjyY")
BOT_TOKEN = raw_token.strip().replace("'", "").replace('"', "")

raw_gemini = os.environ.get("GEMINI_API_KEY", "AIzaSyAlkLe-A78iY_wAWo-cA7H7f7PloGCC5gI")
GEMINI_API_KEY = raw_gemini.strip().replace("'", "").replace('"', "")

# Payment QR Image Name
QR_IMAGE_PATH = "business_qr.jpg" # Make sure file name matches exactly

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize AI (Google Gemini)
ai_model = None
ai_status = "Unknown"

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
        ai_status = "Active ✅"
    except Exception as e:
        ai_status = f"Error: {str(e)}"
else:
    ai_status = "Missing API Key ❌"

# ================= 2. MEDICAL BRAIN (AI LOGIC) =================

def get_medical_advice(user_query, image=None):
    """
    Ye function Dr. Sneha ka dimaag hai.
    Ye bimari sunkar 3 step me ilaj batata hai.
    """
    if not ai_model:
        return f"⚠️ SYSTEM ERROR: AI Brain not connected.\nStatus: {ai_status}\n(Admin: Check Render Environment Variables)"

    # Doctor System Prompt (Instructions)
    doctor_prompt = """
    Act as Dr. Sneha, an expert AI Medical Consultant.
    Language: Hinglish (Hindi + English mix, easy to understand).
    
    Structure your response strictly in these 3 sections:
    
    1. 🚑 **Turant Upay (Immediate Relief):** What to do right now for relief?
    2. 💊 **Dawa aur Course (Medicine):** Suggest generic medicines, dosage, and for how many days.
    3. 🚫 **Parhez aur Savdhani (Precautions):** What to eat/avoid and lifestyle changes.
    
    End with: "Note: Main AI hu. Gambhir samasya ke liye asli Doctor se milen."
    """
    
    try:
        if image:
            # Agar user ne photo bheji hai (Medicine/Report)
            prompt = [doctor_prompt + "\n\nUser ne ye photo bheji hai. Isse analyze karke batao ye kya hai aur kaise use karein:", image]
            response = ai_model.generate_content(prompt)
        else:
            # Agar user ne bimari likh kar bheji hai
            prompt = doctor_prompt + "\n\nPatient ki samasya: " + user_query
            response = ai_model.generate_content(prompt)
            
        return response.text
    except Exception as e:
        return f"⚠️ AI Response Error: {str(e)}. (Check API Quota or Connection)"

# ================= 3. WEB SERVER (KEEP ALIVE) =================
app = Flask(__name__)

@app.route('/')
def home():
    return f"Dr. Sneha is Live! AI Status: {ai_status}"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()

# ================= 4. USER DATABASE & PLANS =================
users_db = {}
PLANS = {
    "49": {"price": 49, "days": 1}, 
    "149": {"price": 149, "days": 15},
    "299": {"price": 299, "days": 30},
    "599": {"price": 599, "days": 90}
}

def is_user_active(user_id):
    # Testing ke liye sabko active mante hain (Demo Mode)
    # Agar Payment system lagana hai to niche wali line uncomment karein:
    # return True if user_id in users_db and users_db[user_id]['expiry'] > datetime.datetime.now() else False
    return True 

# ================= 5. BOT COMMANDS =================

@bot.message_handler(commands=['start', 'test'])
def start(message):
    # Debug Message (User ko batane ke liye ki sab theek hai ya nahi)
    status_msg = f"System Status Check:\n🤖 Bot: Online\n🧠 AI Brain: {ai_status}"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("Plan: ₹49", callback_data="buy_49")
    btn2 = types.InlineKeyboardButton("Plan: ₹149", callback_data="buy_149")
    markup.add(btn1, btn2)
    
    bot.send_message(message.chat.id, 
                     f"Namaste! 🙏 Main Dr. Sneha hu.\n\n{status_msg}\n\nApni bimari likhein ya dawa ki photo bhejein.", 
                     reply_markup=markup)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        img = Image.open(io.BytesIO(downloaded)).convert("RGB")
        
        reply = get_medical_advice("", image=img)
        bot.reply_to(message, reply, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    bot.send_chat_action(message.chat.id, 'typing')
    
    # AI se jawab maango
    reply = get_medical_advice(message.text)
    
    # Jawab bhejo (Markdown format me taki bold/lists dikhe)
    try:
        bot.reply_to(message, reply, parse_mode="Markdown")
    except:
        # Agar Markdown me error aaye to normal text bhejo
        bot.reply_to(message, reply)

# ================= 6. START ENGINE =================
if __name__ == "__main__":
    keep_alive()
    print("--- Dr. Sneha is Starting ---")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot Crash Error: {e}")

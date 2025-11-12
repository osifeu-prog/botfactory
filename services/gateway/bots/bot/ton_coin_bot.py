# bots/ton_coin_bot.py
import telebot
from telebot import types
import json
import asyncio
import threading
from crypto.ton_manager import ton_manager
from config.settings import settings

class TONCoinBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.user_data = {}  # Store user wallet addresses etc.
        self.setup_handlers()
        
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start_handler(message):
            user_id = message.from_user.id
            welcome_text = """
🚀 **ברוך הבא לבוט המטבע TON שלך!**

אני יכול לעזור לך:
• להציג את איזון המטבע שלך
• לשלוח TON לאחרים  
• לקבל TON
• לבדוק מחירים
• לנהל את הארנק שלך

בחר אחת מהאפשרויות:
            """
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row('👛 איזון', '📤 שלח TON')
            markup.row('📥 קבל TON', '📊 מחיר TON')
            markup.row('🔗 כתובת שלי', '🆘 עזרה')
            
            self.bot.send_message(
                message.chat.id, 
                welcome_text, 
                reply_markup=markup,
                parse_mode='Markdown'
            )

        @self.bot.message_handler(commands=['wallet'])
        def wallet_handler(message):
            """Create or show wallet"""
            user_id = message.from_user.id
            if user_id not in self.user_data:
                self.user_data[user_id] = {
                    'wallet_address': 'EQ' + 'X' * 48  # Mock address
                }
            
            wallet_info = f"""
👛 **הארנק שלך:**

**📧 כתובת:**
`{self.user_data[user_id]['wallet_address']}`

**💎 איזון TON:** 0.00 TON
**🪙 מטבעות אישיים:** 0.00

השתמש בכתובת זו כדי לקבל TON או מטבעות.
            """
            self.bot.send_message(message.chat.id, wallet_info, parse_mode='Markdown')

        @self.bot.message_handler(func=lambda message: message.text == '👛 איזון')
        def balance_handler(message):
            user_id = message.from_user.id
            balance_text = """
💎 **איזון TON שלך:**

**ארנק ראשי:** 0.00 TON
**מטבעות מיוחדים:** 0.00 TON

🆔 **כתובת הארנק:**
`EQXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`

*לחץ על "🔗 כתובת שלי" לפרטים מלאים*
            """
            self.bot.send_message(message.chat.id, balance_text, parse_mode='Markdown')

        @self.bot.message_handler(func=lambda message: message.text == '📤 שלח TON')
        def send_handler(message):
            msg = self.bot.send_message(
                message.chat.id, 
                "📤 **שליחת TON**\n\nשלח את כתובת היעד (מתחיל ב-EQ):",
                parse_mode='Markdown'
            )
            self.bot.register_next_step_handler(msg, self.process_address)

        @self.bot.message_handler(func=lambda message: message.text == '📥 קבל TON')
        def receive_handler(message):
            user_id = message.from_user.id
            if user_id not in self.user_data:
                self.user_data[user_id] = {
                    'wallet_address': 'EQ' + 'X' * 48
                }
                
            address_text = f"""
📥 **קבלת TON**

הנה כתובת הארנק שלך לשיתוף:

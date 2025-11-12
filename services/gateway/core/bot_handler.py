# core/bot_handler.py
import os
import json
import time
import requests
import sqlite3
import importlib
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config.settings import settings

# Global data structures
received_messages = []
pending_requests = {}
hourly_activity = [0] * 24  # פעילות לפי שעות
active_bots = {}  # Global bot instances

# Tone integration
try:
    from core.tone_integration import tone_api, TONE_AVAILABLE
except ImportError:
    TONE_AVAILABLE = False
    tone_api = None

# TON integration
try:
    from crypto.ton_manager import ton_manager
    TON_AVAILABLE = True
except ImportError:
    TON_AVAILABLE = False
    ton_manager = None

def find_tokens():
    """
    מצא את כל הטוקנים הזמינים מהסביבה ומקובץ tokens.json
    """
    tokens = {}
    
    try:
        # First try to load from tokens.json
        with open('tokens.json', 'r') as f:
            tokens_data = json.load(f)
        
        for key, token in tokens_data.items():
            if token and token.strip():
                tokens[key] = token.strip()
                print(f"[TOKEN] Found {key} from tokens.json: {token[:8]}...")
    except Exception as e:
        print(f"[ERROR] Error loading tokens.json: {e}")
    
    # Then check environment variables for additional tokens
    custom_tokens = [
        'BOT1_TOKEN1', 'BOT1_TOKEN2', 'BOT1_TOKEN3', 'BOT1_TOKEN4', 'OT1_TOKEN5',
        'BOT6_TOKEN', 'BOT7_TOKEN',  # Tone tokens
        'TON_BOT_TOKEN', 'TON_COIN_BOT'  # TON tokens
    ]
    
    for env_key in custom_tokens:
        token = os.getenv(env_key)
        if token and token.strip():
            tokens[env_key.lower()] = token.strip()
            print(f"[TOKEN] Found {env_key}: {token[:8]}...")
    
    # If no custom tokens found, try standard patterns
    if not tokens:
        for i in range(1, 11):
            for prefix in ['BOT', 'TELEGRAM_BOT']:
                env_key = f"{prefix}{i}_TOKEN"
                token = os.getenv(env_key)
                if token and token.strip():
                    tokens[env_key.lower()] = token.strip()
                    print(f"[TOKEN] Found {env_key}: {token[:8]}...")
                    break
    
    print(f"[TOKEN] Total tokens found: {len(tokens)}")
    return tokens

def create_bot_instance(bot_name: str, token: str):
    """Create bot instance by name"""
    print(f"[BOT_HANDLER] Creating bot instance: {bot_name}")
    
    # Check for TON bot
    if bot_name == 'ton_coin_bot' or 'ton' in bot_name.lower():
        try:
            from bots.ton_coin_bot import create_ton_bot
            bot_instance = create_ton_bot(token)
            print(f"[BOT_HANDLER] Successfully created TON bot instance: {bot_name}")
            return bot_instance
        except Exception as e:
            print(f"[ERROR] Failed to create TON bot {bot_name}: {e}")
            return None
    
    # Check for existing bots with create_bot function
    try:
        module_name = f"bots.{bot_name}"
        module = importlib.import_module(module_name)
        bot_class = getattr(module, 'create_bot', None)
        if bot_class:
            bot_instance = bot_class(token)
            print(f"[BOT_HANDLER] Successfully created {bot_name} instance")
            return bot_instance
        else:
            print(f"[WARNING] No create_bot function found in {module_name}")
            return None
    except Exception as e:
        print(f"[ERROR] Error creating bot {bot_name}: {e}")
        return None

def start_bot(bot_name: str, bot_instance):
    """Start a bot in a separate thread"""
    if bot_instance is None:
        print(f"[ERROR] Cannot start {bot_name} - instance is None")
        return
        
    try:
        def run_bot():
            print(f"[BOT_START] Starting {bot_name}...")
            try:
                if hasattr(bot_instance, 'run'):
                    bot_instance.run()
                elif hasattr(bot_instance, 'polling'):
                    bot_instance.polling()
                elif hasattr(bot_instance, 'infinity_polling'):
                    bot_instance.infinity_polling()
                else:
                    print(f"[WARNING] No run method found for {bot_name}")
            except Exception as e:
                print(f"[ERROR] Bot {bot_name} crashed: {e}")
                # Restart after delay
                time.sleep(10)
                start_bot(bot_name, bot_instance)
        
        bot_thread = threading.Thread(target=run_bot, name=f"BotThread-{bot_name}")
        bot_thread.daemon = True
        bot_thread.start()
        print(f"[BOT_START] {bot_name} thread started")
        
    except Exception as e:
        print(f"[ERROR] Failed to start {bot_name}: {e}")

def initialize_all_bots():
    """Initialize and start all bots"""
    tokens = find_tokens()
    bot_instances = {}
    
    print(f"[INIT] Initializing {len(tokens)} bots...")
    
    for bot_name, token in tokens.items():
        if not token:
            print(f"[SKIP] {bot_name} - no token provided")
            continue
            
        print(f"[INIT] Creating {bot_name}...")
        bot_instance = create_bot_instance(bot_name, token)
        
        if bot_instance:
            bot_instances[bot_name] = bot_instance
            active_bots[bot_name] = bot_instance
            # Start bot in separate thread
            start_bot(bot_name, bot_instance)
        else:
            print(f"[ERROR] Failed to create {bot_name}")
    
    print(f"[INIT] Bot initialization complete. {len(bot_instances)} bots running.")
    return bot_instances

def log_message(user_id, message, bot_token=None):
    """
    רישום הודעה חדשה
    """
    timestamp = datetime.now()
    hour = timestamp.hour
    
    received_messages.append({
        'user_id': user_id,
        'message': message,
        'timestamp': timestamp,
        'bot': bot_token[:8] + '...' if bot_token else 'unknown'
    })
    
    # עדכן סטטיסטיקת פעילות
    hourly_activity[hour] += 1
    
    # שמור רק 1000 הודעות אחרונות
    if len(received_messages) > 1000:
        received_messages.pop(0)

def is_tone_bot(bot_token):
    """בדיקה אם הבוט הוא חלק ממערכת טון"""
    if not TONE_AVAILABLE:
        return False
    
    tone_tokens = [
        '5ff1c8c048bb7f39b515ed354e638b1fe65f831243ab47d53096df0e1f8d8099',
        '50e782e4efe6104c0821a4884412505972a23d14e7dc562030a3da8a41b6fd0f'
    ]
    return bot_token in tone_tokens

def is_ton_bot(bot_name):
    """בדיקה אם הבוט הוא בוט TON"""
    return 'ton' in bot_name.lower()

def handle_ton_message(update, bot_token, bot_name):
    """טיפול מיוחד בהודעות מבוטי TON"""
    try:
        # For TON bots, we let them handle their own messages through their internal logic
        # This function just logs the activity
        user_id = update['message']['from']['id']
        message_text = update['message'].get('text', '')
        
        print(f"[TON] Message from user {user_id} via {bot_name}: {message_text}")
        
        # Log the message for analytics
        log_message(user_id, f"[TON/{bot_name}] {message_text}", bot_token)
        
        return {
            "status": "processed_by_bot", 
            "type": "ton_message",
            "bot": bot_name
        }
        
    except Exception as e:
        print(f"Error handling TON message: {e}")
        return {"status": "error", "error": str(e)}

def handle_tone_message(update, bot_token):
    """טיפול מיוחד בהודעות מבוטי טון"""
    try:
        user_id = update['message']['from']['id']
        message_text = update['message'].get('text', '')
        first_name = update['message']['from'].get('first_name', 'User')
        
        print(f"[TONE] Processing message from user {user_id}: {message_text}")
        
        response_text = "🎵 ברוך הבא למערכת טון!\n\n"
        
        if message_text == '/start':
            response_text += """🤖 אפשרויות טון מתקדמות:

💰 *ניהול ארנק ותשלומים*
/wallet - צפה בארנק שלך
/pay <amount> - בצע תשלום
/invoices - הצג חשבוניות

🖼️ *ניהול NFT*
/nft list - הצג את האוסף שלך
/nft create - צור NFT חדש
/nft info <id> - מידע על NFT

📊 *סטטיסטיקות*
/stats - סטטיסטיקות אישיות
/help - עזרה מפורטת"""

        elif message_text.startswith('/pay'):
            # טיפול בתשלומים
            try:
                amount = float(message_text.split()[1]) if len(message_text.split()) > 1 else 10.0
                payment_result = handle_tone_payment(user_id, amount)
                
                if 'error' not in payment_result:
                    response_text = f"""💰 *תשלום נוצר בהצלחה!*

סכום: {amount} USD
מספר חשבונית: {payment_result['invoice_id']}

לחץ על הקישור לתשלום:
{payment_result.get('payment_url', 'https://tone.pay')}"""
                else:
                    response_text = f"❌ שגיאה ביצירת תשלום: {payment_result['error']}"
                    
            except (IndexError, ValueError):
                response_text = "❌ שימוש: /pay <amount>"

        elif message_text.startswith('/nft'):
            # טיפול ב-NFT
            parts = message_text.split()
            action = parts[1] if len(parts) > 1 else 'list'
            nft_id = parts[2] if len(parts) > 2 else None
            
            nft_result = handle_nft_commands(user_id, action, nft_id)
            
            if 'error' not in nft_result:
                response_text = nft_result['response']
            else:
                response_text = f"❌ שגיאה בפקודת NFT: {nft_result['error']}"

        elif message_text == '/wallet':
            response_text = """💰 *ארנק טון שלך*

יתרת TON: 125.50
יתרת USD: $250.00
נכבי NFT: 3

💸 הכנסות מהשבוע: $45.20
📈 שינוי 24h: +2.3%"""

        elif message_text == '/invoices':
            response_text = """🧾 *חשבוניות אחרונות*

1. INV_12345 - $25.00 - ✅ שולם
2. INV_12346 - $50.00 - ⏳ ממתין
3. INV_12347 - $15.00 - ✅ שולם"""

        elif message_text == '/stats':
            response_text = f"""📊 *סטטיסטיקות אישיות*

👤 משתמש: {first_name}
🆔 ID: {user_id}
📅 משתמש מאת: {datetime.now().strftime('%d/%m/%Y')}

🤖 אינטראקציות: 47
💰 תשלומים: 5
🖼️ NFT: 3"""

        elif message_text == '/help':
            response_text = """📖 *עזרה למערכת טון*

*פקודות בסיסיות*
/start - התחל שיחה
/help - הצג עזרה זו

*ארנק ותשלומים*
/wallet - צפה בארנק
/pay <amount> - בצע תשלום
/invoices - הצג חשבוניות

*ניהול NFT*
/nft list - הצג אוסף
/nft create - צור NFT
/nft info <id> - מידע NFT

*סטטיסטיקות*
/stats - סטטיסטיקות אישיות

לעזרה נוספת: @support"""
        
        else:
            response_text += "לא מזוהה. הקלד /help לרשימת הפקודות"

        # שליחת תגובה
        send_telegram_response(bot_token, user_id, response_text)
        
        # רישום ההודעה
        log_message(user_id, f"[TONE] {message_text}", bot_token)
        
        return {"status": "processed", "type": "tone_message"}
        
    except Exception as e:
        print(f"Error handling tone message: {e}")
        return {"status": "error", "error": str(e)}

def handle_tone_payment(user_id, amount, currency='USD'):
    """טיפול בתשלומים דרך טון"""
    try:
        if not TONE_AVAILABLE:
            return {'error': 'Tone integration not available'}
        
        payment_data = {
            'user_id': user_id,
            'amount': amount,
            'currency': currency,
            'status': 'pending',
            'invoice_id': f"INV_{user_id}_{int(time.time())}",
            'timestamp': datetime.now().isoformat()
        }
        
        # שמור את פרטי התשלום במסד הנתונים
        save_payment_record(payment_data)
        
        return {
            'status': 'success',
            'invoice_id': payment_data['invoice_id'],
            'payment_url': f"https://tone.pay/invoice/{payment_data['invoice_id']}",
            'message': 'Payment invoice created successfully'
        }
        
    except Exception as e:
        print(f"Error handling tone payment: {e}")
        return {'error': str(e)}

def handle_nft_commands(user_id, action, nft_id=None):
    """טיפול בפקודות NFT"""
    try:
        if not TONE_AVAILABLE:
            return {'error': 'Tone integration not available'}
        
        actions = {
            'list': f"🖼️ האוסף NFT שלך:\n• NFT #001 - Digital Art #1\n• NFT #002 - CryptoPunk #42\n• NFT #003 - TON Art #7",
            'create': "🎨 יצירת NFT חדש - תכונה בהרצה...",
            'transfer': f"🔄 העברת NFT {nft_id} - תכונה בהרצה...",
            'info': f"ℹ️ מידע על NFT {nft_id} - פרטים יופיעו כאן..."
        }
        
        response = actions.get(action, "❔ פקודת NFT לא מזוהה. השתמש ב: list, create, transfer, info")
        
        return {
            'status': 'success',
            'action': action,
            'nft_id': nft_id,
            'response': response
        }
        
    except Exception as e:
        print(f"Error handling NFT command: {e}")
        return {'error': str(e)}

def handle_update(update, bot_token=None, bot_name=None):
    """
    טיפול בעדכונים מהבוט - פונקציה שנדרשת ע"י webhook.py
    """
    try:
        if 'message' in update:
            user_id = update['message']['from']['id']
            message_text = update['message'].get('text', '')
            first_name = update['message']['from'].get('first_name', 'User')
            
            # Check if this is a TON bot and handle specially
            if bot_name and is_ton_bot(bot_name):
                return handle_ton_message(update, bot_token, bot_name)
            
            # בדיקה אם זה בוט טון וטיפול מיוחד
            if is_tone_bot(bot_token):
                return handle_tone_message(update, bot_token)
            
            # רישום ההודעה
            log_message(user_id, message_text, bot_token)
            
            # טיפול רגיל בהודעות
            response_text = ""
            if message_text == '/start':
                response_text = f"""👋 שלום {first_name}!

ברוך הבא לבוט הפקטורי! 

🤖 אני כאן כדי לעזור לך עם:
• ניהול חשבון
• הפניות וחברים
• עסקאות קריפטו

הקלק /help לעזרה נוספת."""
            elif message_text == '/help':
                response_text = """📖 **עזרה:**

פקודות זמינות:
/start - התחל שיחה
/help - הצג עזרה
/wallet - צפה בארנק שלך
/referral - קבל לינק הפניה

Need help? Contact support."""
            else:
                response_text = "🤖 I received your message. Type /help for available commands."
            
            # Send response back to user
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": user_id,
                        "text": response_text,
                        "parse_mode": "HTML"
                    },
                    timeout=10
                )
                print(f"[BOT] Sent response to user {user_id}: {message_text}")
            except Exception as e:
                print(f"[BOT] Error sending response: {e}")
            
            return {"status": "processed", "type": "message"}
            
        elif 'callback_query' in update:
            return handle_callback_query(update['callback_query'], bot_token)
            
    except Exception as e:
        print(f"Error handling update: {e}")
        return {"status": "error", "error": str(e)}
    
    return {"status": "ignored"}

def handle_callback_query(callback_query, bot_token=None):
    """
    טיפול בכפתורים ואינטראקציות - פונקציה שנדרשת ע"י webhook.py
    """
    try:
        user_id = callback_query['from']['id']
        data = callback_query.get('data', '')
        
        # רישום האינטראקציה
        log_message(user_id, f"Callback: {data}", bot_token)
        
        # כאן תוכל להוסיף לוגיקה נוספת לטיפול באינטראקציות
        return {"status": "processed", "type": "callback"}
        
    except Exception as e:
        print(f"Error handling callback: {e}")
        return {"status": "error", "error": str(e)}

def send_telegram_response(bot_token, chat_id, text):
    """שליחת תגובה דרך Telegram API"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
    except Exception as e:
        print(f"Error sending response: {e}")

def save_payment_record(payment_data):
    """שמירת רשומת תשלום במסד הנתונים"""
    try:
        conn = sqlite3.connect('data/bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tone_payments (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                currency TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT OR REPLACE INTO tone_payments 
            (invoice_id, user_id, amount, currency, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            payment_data['invoice_id'],
            payment_data['user_id'],
            payment_data['amount'],
            payment_data['currency'],
            payment_data['status']
        ))
        
        conn.commit()
        conn.close()
        print(f"Payment record saved: {payment_data['invoice_id']}")
        
    except Exception as e:
        print(f"Error saving payment record: {e}")

def add_pending_request(user_id, username, request_type, details):
    """
    הוספת בקשה ממתינה לאישור
    """
    entry_id = f"{user_id}_{int(time.time())}"
    
    pending_requests[entry_id] = {
        'user_id': user_id,
        'username': username,
        'type': request_type,
        'details': details,
        'timestamp': datetime.now(),
        'status': 'pending'
    }
    
    return entry_id

def admin_approve_request(entry_id, approved_by):
    """
    אישור בקשה על ידי אדמין
    """
    if entry_id not in pending_requests:
        return False, "Request not found"
    
    request_data = pending_requests[entry_id]
    request_data['status'] = 'approved'
    request_data['approved_by'] = approved_by
    request_data['approved_at'] = datetime.now()
    
    return True, "Request approved"

def admin_reject_request(entry_id, reason, rejected_by):
    """
    דחיית בקשה על ידי אדמין
    """
    if entry_id not in pending_requests:
        return False, "Request not found"
    
    request_data = pending_requests[entry_id]
    request_data['status'] = 'rejected'
    request_data['rejected_by'] = rejected_by
    request_data['rejection_reason'] = reason
    request_data['rejected_at'] = datetime.now()
    
    return True, "Request rejected"

def hourly_activity_counts():
    """
    מחזיר סטטיסטיקת פעילות לפי שעות
    """
    return hourly_activity

def generate_referral_link_for_user(bot_token, user_id):
    """
    יצירת לינק הפניה למשתמש
    """
    try:
        # קבלת מידע על הבוט
        response = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe")
        if response.status_code == 200:
            bot_info = response.json()
            if bot_info.get('ok'):
                bot_username = bot_info['result']['username']
                return f"https://t.me/{bot_username}?start=ref{user_id}"
    except Exception as e:
        print(f"Error generating referral link: {e}")
    
    return None

def get_leaderboard(limit=10):
    """
    מחזיר טבלת לידרים של משתמשים לפי נקודות
    """
    try:
        conn = sqlite3.connect('data/bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, points, referrals 
            FROM user_points 
            ORDER BY points DESC 
            LIMIT ?
        ''', (limit,))
        
        leaderboard = []
        for row in cursor.fetchall():
            leaderboard.append({
                'user_id': row[0],
                'username': row[1] or f"User_{row[0]}",
                'points': row[2],
                'referrals': row[3]
            })
        
        conn.close()
        return leaderboard
    except Exception as e:
        print(f"Error getting leaderboard: {e}")
        return []

def get_points_for_user(user_id):
    """
    מחזיר נקודות עבור משתמש ספציפי
    """
    try:
        conn = sqlite3.connect('data/bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT points, referrals FROM user_points WHERE user_id = ?',
            (user_id,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {'points': result[0], 'referrals': result[1]}
        else:
            return {'points': 0, 'referrals': 0}
    except Exception as e:
        print(f"Error getting points for user: {e}")
        return {'points': 0, 'referrals': 0}

def load_referrals():
    """
    טעינת נתוני הפניות
    """
    try:
        conn = sqlite3.connect('data/bot_data.db')
        cursor = conn.cursor()
        
        # טען נתוני הפניות
        cursor.execute('SELECT referrer_id, referred_id, bot_token, timestamp FROM referrals')
        referrals_data = cursor.fetchall()
        
        # ארגן לפי מפנה
        by_referrer = {}
        for ref in referrals_data:
            referrer_id, referred_id, bot_token, timestamp = ref
            if referrer_id not in by_referrer:
                by_referrer[referrer_id] = []
            
            by_referrer[referrer_id].append({
                'referred': referred_id,
                'bot': bot_token,
                'ts': timestamp
            })
        
        conn.close()
        
        return {
            'by_referrer': by_referrer,
            'total_referrals': len(referrals_data)
        }
    except Exception as e:
        print(f"Error loading referrals: {e}")
        return {'by_referrer': {}, 'total_referrals': 0}

def get_system_stats():
    """
    מחזיר סטטיסטיקות מערכת כולל TON
    """
    tokens = find_tokens()
    
    # ספירת הודעות
    message_count = len(received_messages)
    
    # ספירת בקשות ממתינות
    pending_count = len([r for r in pending_requests.values() if r['status'] == 'pending'])
    
    # TON stats
    ton_bots = [name for name in tokens.keys() if 'ton' in name.lower()]
    
    stats = {
        'status': 'healthy',
        'message_count': message_count,
        'pending_count': pending_count,
        'total_bots': len(tokens),
        'active_bots': list(tokens.keys()),
        'ton_bots_count': len(ton_bots),
        'ton_network': 'testnet',
        'ton_api_status': 'connected' if TON_AVAILABLE else 'disabled',
        'tone_integration': 'active' if TONE_AVAILABLE else 'disabled',
        'timestamp': time.time(),
        'memory_usage': 'normal'
    }
    
    # Add TON-specific stats if available
    if TON_AVAILABLE:
        stats["ton_settings"] = {
            "network": "testnet",
            "api_keys_configured": True,
            "contract_ready": False
        }
    
    return stats

def get_all_bots_health():
    """
    Check health of all bots by testing their webhook info
    Returns a dictionary with health status for each bot
    """
    tokens = find_tokens()
    health_data = {}
    
    for env_key, token in tokens.items():
        if not token:
            health_data[env_key] = {
                'status': 'invalid',
                'error': 'Token is empty or missing'
            }
            continue
            
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{token}/getWebhookInfo",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                health_data[env_key] = {
                    'status': 'healthy' if data.get('ok') else 'error',
                    'webhook_info': data
                }
            else:
                health_data[env_key] = {
                    'status': 'error',
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except Exception as e:
            health_data[env_key] = {
                'status': 'error',
                'error': str(e)
            }
    
    return health_data

def get_tone_stats():
    """
    סטטיסטיקות ספציפיות למערכת טון
    """
    try:
        conn = sqlite3.connect('data/bot_data.db')
        cursor = conn.cursor()
        
        # בדוק אם טבלת תשלומי טון קיימת
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='tone_payments'
        ''')
        
        if cursor.fetchone():
            # ספירת תשלומים
            total_payments = conn.execute("SELECT COUNT(*) FROM tone_payments").fetchone()[0]
            successful_payments = conn.execute("SELECT COUNT(*) FROM tone_payments WHERE status='completed'").fetchone()[0]
            total_amount = conn.execute("SELECT SUM(amount) FROM tone_payments WHERE status='completed'").fetchone()[0] or 0
        else:
            total_payments = 0
            successful_payments = 0
            total_amount = 0
        
        conn.close()
        
        return {
            'total_payments': total_payments,
            'successful_payments': successful_payments,
            'total_amount': round(total_amount, 2),
            'tone_bots_count': 2  # BOT6_TOKEN and BOT7_TOKEN
        }
        
    except Exception as e:
        print(f"Error getting tone stats: {e}")
        return {
            'total_payments': 0,
            'successful_payments': 0,
            'total_amount': 0,
            'tone_bots_count': 2
        }

def stop_all_bots():
    """Stop all running bots (for graceful shutdown)"""
    print("[SHUTDOWN] Stopping all bots...")
    # Implementation would depend on how bots are structured
    global active_bots
    active_bots = {}

# אתחול בסיסי של מסד הנתונים
def init_database():
    """
    אתחול טבלאות במסד הנתונים
    """
    try:
        os.makedirs('data', exist_ok=True)
        
        conn = sqlite3.connect('data/bot_data.db')
        cursor = conn.cursor()
        
        # טבלת נקודות משתמשים
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_points (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                points INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # טבלת הפניות
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                bot_token TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # טבלת תשלומי טון
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tone_payments (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                currency TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")

# אתחול אוטומטי
init_database()

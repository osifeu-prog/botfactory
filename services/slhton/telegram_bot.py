import os
import json
import logging
from typing import Any, Dict, Optional, List

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
BOT_API_USER = os.getenv("BOT_API_USER", "")
BOT_API_PASS = os.getenv("BOT_API_PASS", "")

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not set")
if not API_BASE_URL:
    logger.error("❌ PUBLIC_BASE_URL not set")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

ADMIN_OWNER_IDS_RAW = os.getenv("ADMIN_OWNER_IDS", "").strip()
ADMIN_OWNER_IDS: List[int] = []
for part in ADMIN_OWNER_IDS_RAW.split(","):
    part = part.strip()
    if not part:
        continue
    try:
        ADMIN_OWNER_IDS.append(int(part))
    except ValueError:
        pass
ADMIN_OWNER_IDS = list(dict.fromkeys(ADMIN_OWNER_IDS))

def is_admin_user(from_user: Dict[str, Any]) -> bool:
    uid = from_user.get("id")
    return bool(uid and uid in ADMIN_OWNER_IDS)

def call_telegram_api(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = TELEGRAM_API_URL + method
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok", False):
            logger.error(f"Telegram API error for {method}: {data}")
        return data
    except Exception as e:
        logger.error(f"Failed to call Telegram API {method}: {e}")
        return {"ok": False}

def send_message(chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> None:
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        call_telegram_api("sendMessage", payload)
    except Exception as e:
        logger.exception("Failed to send_message: %s", e)

def call_local_api(
    path: str,
    payload: Optional[Dict[str, Any]],
    method: str = "POST",
    use_auth: bool = True,
) -> Any:
    if not API_BASE_URL:
        raise RuntimeError("PUBLIC_BASE_URL env var is not set")
    url = API_BASE_URL + path

    auth = (BOT_API_USER, BOT_API_PASS) if use_auth and BOT_API_USER and BOT_API_PASS else None
    headers = {"Content-Type": "application/json"}

    try:
        method = method.upper()
        if method == "GET":
            resp = requests.get(url, params=payload or {}, headers=headers, auth=auth, timeout=10)
        else:
            data = json.dumps(payload or {})
            resp = requests.post(url, data=data, headers=headers, auth=auth, timeout=10)

        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return resp.text
    except requests.exceptions.RequestException as e:
        logger.error(f"API call failed to {url}: {e}")
        raise RuntimeError(f"Failed to connect to API: {e}")

def send_welcome(chat_id: int) -> None:
    text = (
        "🚀 **ברוך הבא ל-SLHTON!**\n\n"
        "**פקודות זמינות:**\n"
        "/register - הרשמה למערכת\n"
        "/addwallet - הוספת ארנק\n" 
        "/deposit - הפקדת מטבעות\n"
        "/createorder - יצירת הזמנה\n"
        "/fillorder - מילוי הזמנה\n"
        "/orders - הצגת ההזמנות שלי\n"
        "/bankinfo - פרטי תשלום\n"
        "/help - הצגת עזרה\n\n"
        "המערכת מוכנה לפעולה! ✨"
    )
    send_message(chat_id, text)

def send_bankinfo(chat_id: int) -> None:
    text = (
        "🏦 **פרטי התשלום להצטרפות:**\n\n"
        "**בנק:** הפועלים\n"
        "**סניף:** כפר גנים (153)\n" 
        "**חשבון:** 73462\n"
        "**המוטב:** קאופמן צביקה\n"
        "**סכום:** 39 ש\"ח\n\n"
        "לאחר ההעברה:\n"
        "1. שלחו צילום/אישור העברה לבוט\n"
        "2. המתינו לאישור אדמין\n"
        "3. קבלו את מטבעות SLH לחשבון\n\n"
        "✅ תודה שבחרתם ב-SLHTON!"
    )
    send_message(chat_id, text)

def handle_update(update: Dict[str, Any]) -> bool:
    logger.info(f"📥 Processing update: {update.get('update_id')}")
    
    if "callback_query" in update:
        callback = update["callback_query"]
        data = callback.get("data", "")
        from_user = callback.get("from", {})
        
        if data.startswith("payok:") or data.startswith("payno:"):
            if not is_admin_user(from_user):
                return True
            parts = data.split(":")
            if len(parts) >= 3:
                user_chat_id = parts[1]
                action = "אושר" if data.startswith("payok:") else "נדחה"
                send_message(int(user_chat_id), f"📋 **סטטוס תשלום:** {action}")
            return True
        
        elif data == "admin:chatinfo":
            chat = callback.get("message", {}).get("chat", {})
            send_message(chat.get("id", 0), f"💬 Chat ID: {chat.get('id')}")
            return True
            
        elif data == "admin:whoami":
            user = callback.get("from", {})
            send_message(user.get("id", 0), f"👤 User ID: {user.get('id')}")
            return True
        
        return True

    message = update.get("message") or update.get("edited_message")
    if not message:
        return False

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return False

    text = (message.get("text") or "").strip()
    from_user = message.get("from", {})
    
    logger.info(f"💬 Message from {from_user.get('id')}: {text}")

    if not text:
        return False

    try:
        if text.startswith("/start") or text.startswith("/help"):
            send_welcome(chat_id)
            return True

        elif text.startswith("/bankinfo"):
            send_bankinfo(chat_id)
            return True

        elif text.startswith("/register"):
            parts = text.split()
            if len(parts) == 3:
                username, password = parts[1], parts[2]
                try:
                    resp = call_local_api("/register", {"username": username, "password": password}, "POST", False)
                    send_message(chat_id, f"✅ **הרשמה בוצעה:** {username}")
                except Exception as e:
                    send_message(chat_id, f"❌ **שגיאה בהרשמה:** {e}")
            else:
                send_message(chat_id, "❌ **שימוש:** /register username password")
            return True

        elif text.startswith("/orders"):
            try:
                resp = call_local_api("/orders", None, "GET")
                if resp and isinstance(resp, list):
                    orders_text = "📋 **ההזמנות שלי:**\n\n"
                    for order in resp[:5]:  # רק 5 הזמנות ראשונות
                        orders_text += f"#{order['id']} {order['type']} {order['token']} - {order['amount']} במחיר {order['price_per_token']}\n"
                    send_message(chat_id, orders_text)
                else:
                    send_message(chat_id, "📭 **אין הזמנות פעילות**")
            except Exception as e:
                send_message(chat_id, f"❌ **שגיאה בטעינת הזמנות:** {e}")
            return True

        else:
            send_message(chat_id, "❓ **פקודה לא מזוהה.** נסה /help לרשימת פקודות")
            return True

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        send_message(chat_id, "⚠️ **שגיאה בעיבוד הפקודה.** נסה שוב מאוחר יותר.")
        return True

    return False

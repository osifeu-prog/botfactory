import os
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_webhook():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found in environment variables")
        return

    if not PUBLIC_BASE_URL:
        logger.error("❌ PUBLIC_BASE_URL not found in environment variables")
        return

    webhook_url = f"{PUBLIC_BASE_URL}/telegram/webhook"

    logger.info("🚀 Initializing Telegram Bot Webhook")
    logger.info(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    logger.info(f"🌐 Webhook URL: {webhook_url}")

    # בדוק אם הבוט תקין
    try:
        response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
        bot_info = response.json()
        if bot_info.get('ok'):
            logger.info(f"✅ Bot is valid: @{bot_info['result']['username']}")
        else:
            logger.error(f"❌ Bot token invalid: {bot_info}")
            return
    except Exception as e:
        logger.error(f"❌ Error checking bot: {e}")
        return

    # הגדר את webhook
    webhook_payload = {
        "url": webhook_url,
        "max_connections": 40,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True
    }

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json=webhook_payload,
            timeout=10
        )
        webhook_result = response.json()
        logger.info(f"📡 Webhook response: {webhook_result}")

        if webhook_result.get('ok'):
            logger.info("✅ Webhook set successfully!")
        else:
            logger.error(f"❌ Failed to set webhook: {webhook_result}")
            return
    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")
        return

    # בדוק את סטטוס ה-webhook
    try:
        response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo", timeout=10)
        webhook_info = response.json()
        logger.info(f"📊 Webhook info: {webhook_info}")
    except Exception as e:
        logger.error(f"❌ Error checking webhook: {e}")
        return

    logger.info("🎉 Bot is ready! Send /start to your bot.")

if __name__ == "__main__":
    initialize_webhook()

# main.py
from core.webhook import app as webhook_app
from admin.dashboard import app as admin_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
import os
import requests
import threading
import time
from config.settings import settings
from core.bot_handler import initialize_all_bots, find_tokens

def setup_webhooks():
    print("[INIT] Setting up webhooks...")
    
    # Use the improved token finding function
    tokens = find_tokens()
    
    if not tokens:
        print("[WARNING] No tokens found!")
        return
    
    print(f"[INFO] Found {len(tokens)} bots to configure")
    
    for idx, (key, token) in enumerate(tokens.items(), 1):
        if not token:
            print(f"[SKIP] {key} empty")
            continue
            
        bot_path = f"{settings.DOMAIN}/bot{idx}"
        set_webhook_url = f"https://api.telegram.org/bot{token}/setWebhook"
        
        try:
            r = requests.post(
                set_webhook_url, 
                data={"url": bot_path}, 
                timeout=settings.REQUEST_TIMEOUT
            )
            if r.status_code == 200:
                print(f"[OK] Set webhook for {key} -> {bot_path}")
            else:
                print(f"[FAIL] {key}: {r.status_code} {r.text}")
        except Exception as e:
            print(f"[ERROR] {key} setWebhook exception: {e}")

def initialize_ton_bots():
    """Initialize TON and other bots in background"""
    print("[INIT] Starting bot initialization...")
    
    # Small delay to ensure web server is starting
    time.sleep(2)
    
    # Initialize all bots
    bot_instances = initialize_all_bots()
    
    print(f"[INIT] Bot initialization complete. {len(bot_instances)} bots running.")
    return bot_instances

# Health check endpoint for monitoring
def create_health_app():
    from flask import Flask, jsonify
    health_app = Flask(__name__)
    
    @health_app.route('/health')
    def health():
        from core.bot_handler import find_tokens, get_system_stats
        tokens = find_tokens()
        stats = get_system_stats()
        
        return jsonify({
            "status": "healthy",
            "bot_count": len(tokens),
            "active_bots": stats["active_bots"],
            "ton_network": stats["ton_network"],
            "ton_api_status": stats["ton_api_status"],
            "timestamp": stats["timestamp"],
            "system_stats": stats
        })
    
    @health_app.route('/ton-status')
    def ton_status():
        """Specific TON network status"""
        return jsonify({
            "ton_network": "testnet",
            "api_connected": True,
            "wallets_active": 0,
            "transactions_today": 0,
            "last_block": 12345678
        })
    
    return health_app

# Create main application
application = DispatcherMiddleware(webhook_app, {
    "/admin": admin_app,
    "/health": create_health_app()
})

if __name__ == "__main__":
    print("[INFO] Starting Bot Factory Server with TON Support")
    print(f"[INFO] Domain: {settings.DOMAIN}")
    print(f"[INFO] Admin Chat ID: {settings.ADMIN_CHAT_ID}")
    
    # Setup webhooks on startup
    setup_webhooks()
    
    # Initialize bots in background thread
    bot_thread = threading.Thread(target=initialize_ton_bots, name="BotInitializer")
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start development server
    print("[INFO] Starting development server on http://0.0.0.0:8080")
    run_simple(
        "0.0.0.0", 
        8080, 
        application, 
        use_reloader=False, 
        use_debugger=False,
        threaded=True
    )
else:
    # When running in production (e.g., gunicorn), setup webhooks and bots
    setup_webhooks()
    
    # Start bots in background
    bot_thread = threading.Thread(target=initialize_ton_bots, name="BotInitializer")
    bot_thread.daemon = True
    bot_thread.start()

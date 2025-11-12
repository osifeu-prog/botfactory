import os
from flask import Flask, request, jsonify
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv
import logging
import requests
import threading
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

from models import Base, User, Wallet, Balance, Order
from wallet import encrypt_private_key, decrypt_private_key, generate_wallet_from_privkey
from exchange import deposit_token, withdraw_token, create_order, fill_order
from onchain import make_transfer_build_boc_only, send_boc_via_toncenter, get_tx_status
import telegram_bot

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///exchange.db")
WALLET_MASTER_KEY = os.getenv("WALLET_MASTER_KEY", "")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))

try:
    from sqlalchemy import inspect as _sa_inspect
    inspector = _sa_inspect(engine)
    if "users" not in inspector.get_table_names():
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"DB init skipped or failed: {e}")

app = Flask(__name__)
auth = HTTPBasicAuth()

def initialize_webhook():
    """אתחול webhook בהפעלת האפליקציה"""
    time.sleep(5)  # המתן שהאפליקציה תתחיל
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

# הפעל את אתחול ה-webhook ברקע
webhook_thread = threading.Thread(target=initialize_webhook)
webhook_thread.daemon = True
webhook_thread.start()

@auth.verify_password
def verify_password(username, password):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            return user
        return None
    finally:
        db.close()

@app.teardown_appcontext
def remove_session(exception=None):
    SessionLocal.remove()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    db = SessionLocal()
    try:
        if db.query(User).filter_by(username=username).first():
            return jsonify({"error": "user exists"}), 400
        u = User(username=username, password_hash=generate_password_hash(password))
        db.add(u)
        db.commit()
        return jsonify({"ok": True, "username": username}), 200
    finally:
        db.close()

@app.route("/wallets", methods=["GET"])
@auth.login_required
def list_wallets():
    db = SessionLocal()
    try:
        user = auth.current_user()
        wallets = db.query(Wallet).filter_by(user_id=user.id).all()
        return jsonify(
            [
                {
                    "id": w.id,
                    "address": w.address,
                    "pubkey": w.pubkey,
                }
                for w in wallets
            ]
        )
    finally:
        db.close()

@app.route("/wallets/add", methods=["POST"])
@auth.login_required
def add_wallet():
    if not WALLET_MASTER_KEY:
        return jsonify({"error": "WALLET_MASTER_KEY not configured"}), 500
    data = request.get_json(force=True, silent=True) or {}
    privkey_hex = (data.get("privkey_hex") or "").strip()
    if not privkey_hex:
        return jsonify({"error": "privkey_hex required"}), 400
    db = SessionLocal()
    try:
        user = auth.current_user()
        wallet_data = generate_wallet_from_privkey(privkey_hex)
        enc = encrypt_private_key(privkey_hex, WALLET_MASTER_KEY)
        w = Wallet(
            user_id=user.id,
            address=wallet_data["address"],
            pubkey=wallet_data["pubkey"],
            encrypted_privkey=enc,
        )
        db.add(w)
        db.commit()
        db.refresh(w)
        return jsonify(
            {
                "id": w.id,
                "address": w.address,
                "pubkey": w.pubkey,
            }
        )
    finally:
        db.close()

@app.route("/balances/deposit", methods=["POST"])
@auth.login_required
def api_deposit():
    data = request.get_json(force=True, silent=True) or {}
    wallet_id = data.get("wallet_id")
    token = (data.get("token") or "").strip()
    amount = data.get("amount")
    if wallet_id is None or not token or amount is None:
        return jsonify({"error": "wallet_id, token, amount required"}), 400
    db = SessionLocal()
    try:
        user = auth.current_user()
        wallet = db.query(Wallet).filter_by(id=wallet_id, user_id=user.id).first()
        if not wallet:
            return jsonify({"error": "wallet not found"}), 404
        new_amount = deposit_token(db, wallet.id, token, float(amount))
        return jsonify({"wallet_id": wallet.id, "token": token, "balance": new_amount})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@app.route("/balances", methods=["GET"])
@auth.login_required
def api_balances():
    wallet_id = request.args.get("wallet_id", type=int)
    db = SessionLocal()
    try:
        user = auth.current_user()
        q = db.query(Balance).join(Wallet).filter(Wallet.user_id == user.id)
        if wallet_id is not None:
            q = q.filter(Balance.wallet_id == wallet_id)
        balances = q.all()
        return jsonify(
            [
                {
                    "wallet_id": b.wallet_id,
                    "token": b.token,
                    "amount": b.amount,
                }
                for b in balances
            ]
        )
    finally:
        db.close()

@app.route("/orders/create", methods=["POST"])
@auth.login_required
def api_create_order():
    data = request.get_json(force=True, silent=True) or {}
    wallet_id = data.get("wallet_id")
    order_type = (data.get("type") or "").lower()
    token = (data.get("token") or "").strip()
    amount = data.get("amount")
    price = data.get("price_per_token")
    if wallet_id is None or not order_type or not token or amount is None or price is None:
        return jsonify({"error": "wallet_id, type, token, amount, price_per_token required"}), 400
    db = SessionLocal()
    try:
        user = auth.current_user()
        wallet = db.query(Wallet).filter_by(id=wallet_id, user_id=user.id).first()
        if not wallet:
            return jsonify({"error": "wallet not found"}), 404
        order = create_order(db, wallet.id, order_type, token, float(amount), float(price))
        return jsonify(
            {
                "id": order.id,
                "wallet_id": order.wallet_id,
                "type": order.type,
                "token": order.token,
                "amount": order.amount,
                "price_per_token": order.price_per_token,
                "status": order.status,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@app.route("/orders/fill", methods=["POST"])
@auth.login_required
def api_fill_order():
    data = request.get_json(force=True, silent=True) or {}
    order_id = data.get("order_id")
    taker_wallet_id = data.get("taker_wallet_id")
    if order_id is None or taker_wallet_id is None:
        return jsonify({"error": "order_id and taker_wallet_id required"}), 400
    db = SessionLocal()
    try:
        user = auth.current_user()
        taker_wallet = db.query(Wallet).filter_by(id=taker_wallet_id, user_id=user.id).first()
        if not taker_wallet:
            return jsonify({"error": "taker wallet not found"}), 404
        order = fill_order(db, int(order_id), taker_wallet.id)
        return jsonify(
            {
                "id": order.id,
                "wallet_id": order.wallet_id,
                "type": order.type,
                "token": order.token,
                "amount": order.amount,
                "price_per_token": order.price_per_token,
                "status": order.status,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@app.route("/orders", methods=["GET"])
@auth.login_required
def api_list_orders():
    status = (request.args.get("status") or "").strip().lower()
    db = SessionLocal()
    try:
        user = auth.current_user()
        q = db.query(Order).join(Wallet).filter(Wallet.user_id == user.id)
        if status:
            q = q.filter(Order.status == status)
        orders = q.order_by(Order.id.desc()).all()
        return jsonify(
            [
                {
                    "id": o.id,
                    "wallet_id": o.wallet_id,
                    "type": o.type,
                    "token": o.token,
                    "amount": o.amount,
                    "price_per_token": o.price_per_token,
                    "status": o.status,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ]
        )
    finally:
        db.close()

@app.route("/onchain/transfer", methods=["POST"])
@auth.login_required
def api_onchain_transfer():
    if not WALLET_MASTER_KEY:
        return jsonify({"error": "WALLET_MASTER_KEY not configured"}), 500
    data = request.get_json(force=True, silent=True) or {}
    wallet_id = data.get("wallet_id")
    dest_address = (data.get("dest_address") or "").strip()
    amount_nano = data.get("amount_nano")
    comment = data.get("comment")
    if wallet_id is None or not dest_address or amount_nano is None:
        return jsonify({"error": "wallet_id, dest_address, amount_nano required"}), 400
    db = SessionLocal()
    try:
        user = auth.current_user()
        wallet = db.query(Wallet).filter_by(id=wallet_id, user_id=user.id).first()
        if not wallet:
            return jsonify({"error": "wallet not found"}), 404
        priv_hex = decrypt_private_key(wallet.encrypted_privkey, WALLET_MASTER_KEY)
        boc = make_transfer_build_boc_only(wallet.address, priv_hex, dest_address, int(amount_nano), comment)
        result = send_boc_via_toncenter(boc, priv_hex)
        return jsonify({"wallet_id": wallet.id, "dest_address": dest_address, "boc": boc, "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

@app.route("/onchain/status", methods=["GET"])
def api_onchain_status():
    tx_hash = (request.args.get("tx_hash") or "").strip()
    if not tx_hash:
        return jsonify({"error": "tx_hash required"}), 400
    try:
        status = get_tx_status(tx_hash)
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    try:
        update = request.get_json(force=True)
        logger.info(f"📨 Received Telegram update: {update}")
    except Exception as e:
        logger.error(f"❌ Invalid JSON in webhook: {e}")
        return jsonify({"error": "invalid json", "detail": str(e)}), 400
        
    try:
        res = telegram_bot.handle_update(update)
        logger.info(f"✅ Telegram update handled: {res}")
    except Exception as e:
        logger.exception("💥 Telegram handle error")
        return jsonify({"status": "error", "detail": str(e)}), 200
        
    return jsonify({"status": "ok", "handled": bool(res)}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

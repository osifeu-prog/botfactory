# admin/dashboard.py
from flask import Flask, render_template, request, jsonify, Response
import os
import json
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
import sqlite3
import logging

from core.bot_handler import (
    received_messages, pending_requests, admin_approve_request, 
    admin_reject_request, hourly_activity_counts, generate_referral_link_for_user,
    get_leaderboard, get_points_for_user, load_referrals, get_system_stats,
    get_all_bots_health, get_tone_stats, TONE_AVAILABLE
)

app = Flask(__name__)

# Config
from config.settings import settings

class DashboardConfig:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

app.config.from_object(DashboardConfig)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_webhook_summary():
    """מחזיר סיכום של הגדרות ה-webhook"""
    summary = []
    from core.bot_handler import find_tokens
    tokens = find_tokens()
    
    for idx, (key, token) in enumerate(tokens, 1):
        summary.append({
            'env_key': key,
            'bot_index': idx,
            'has_token': bool(token and token.strip()),
            'token_preview': token[:8] + '...' if token else 'None',
            'is_tone': 'BOT6' in key or 'BOT7' in key or '5ff1c8c0' in token or '50e782e4' in token
        })
    
    return summary

def create_activity_plot():
    """יוצר גרף פעילות base64"""
    try:
        counts = hourly_activity_counts()
        
        plt.figure(figsize=(10, 4))
        hours = list(range(24))
        values = [counts[h] for h in hours]
        
        plt.bar(hours, values, color='skyblue', alpha=0.7)
        plt.xlabel('שעה ביום')
        plt.ylabel('מספר הודעות')
        plt.title('פעילות לפי שעות')
        plt.grid(True, alpha=0.3)
        plt.xticks(hours)
        
        # Save to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        plot_b64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        return plot_b64
    except Exception as e:
        logger.error(f"Error creating activity plot: {e}")
        return ""

def get_crypto_stats():
    """Get cryptocurrency statistics for dashboard"""
    try:
        # Check if wallets database exists
        if not os.path.exists('data/wallets.db'):
            return {
                'crypto_wallet_count': 0,
                'crypto_transaction_count': 0
            }
            
        conn = sqlite3.connect('data/wallets.db')
        
        # Wallet count
        wallet_count = conn.execute("SELECT COUNT(*) FROM user_wallets").fetchone()[0]
        
        # Today's transactions
        today = datetime.now().date().isoformat()
        transaction_count = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE date(created_at) = ?", 
            (today,)
        ).fetchone()[0]
        
        conn.close()
        
        return {
            'crypto_wallet_count': wallet_count,
            'crypto_transaction_count': transaction_count
        }
    except Exception as e:
        logger.error(f"Error getting crypto stats: {e}")
        return {
            'crypto_wallet_count': 0,
            'crypto_transaction_count': 0
        }

@app.route('/')
def dashboard():
    """דף הדשבורד הראשי"""
    try:
        system_stats = get_system_stats()
        crypto_stats = get_crypto_stats()
        tone_stats = get_tone_stats()
        
        # Get token info safely
        try:
            from config.blockchain import blockchain_config
            token_price = blockchain_config.TOKEN_PRICE_USD
            token_symbol = blockchain_config.TOKEN_SYMBOL
        except ImportError:
            token_price = 0.01
            token_symbol = "YTT"
        
        webhook_summary = get_webhook_summary()
        tone_bots = [bot for bot in webhook_summary if bot['is_tone']]
        
        context = {
            'system': {
                'domain': settings.DOMAIN,
                'bot_count': len(webhook_summary),
                'tone_bot_count': len(tone_bots),
                'message_count': system_stats['message_count'],
                'pending_count': system_stats['pending_count'],
                'connection_errors': system_stats['connection_errors'],
                'successful_sends': system_stats['successful_sends'],
                'send_failures': system_stats['send_failures'],
                'token_price': token_price,
                'token_symbol': token_symbol,
                'crypto_wallet_count': crypto_stats['crypto_wallet_count'],
                'crypto_transaction_count': crypto_stats['crypto_transaction_count'],
                'tone_payments_count': tone_stats['total_payments'],
                'tone_total_amount': tone_stats['total_amount']
            },
            'webhook_summary': webhook_summary,
            'tone_bots': tone_bots,
            'plot_b64': create_activity_plot(),
            'pending': list(pending_requests.values())[-10:],  # Only show last 10
            'leaderboard': get_leaderboard(),
            'messages': received_messages[-20:][::-1],  # 20 האחרונים
            'tone_available': TONE_AVAILABLE
        }
        
        return render_template('dashboard.html', **context)
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/tone')
def tone_dashboard():
    """דשבורד ניהול ספציפי למערכת טון"""
    try:
        tone_stats = get_tone_stats()
        webhook_summary = get_webhook_summary()
        tone_bots = [bot for bot in webhook_summary if bot['is_tone']]
        
        # Get recent tone payments
        recent_payments = []
        try:
            conn = sqlite3.connect('data/bot_data.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT invoice_id, user_id, amount, currency, status, created_at 
                FROM tone_payments 
                ORDER BY created_at DESC 
                LIMIT 10
            ''')
            
            for row in cursor.fetchall():
                recent_payments.append({
                    'invoice_id': row[0],
                    'user_id': row[1],
                    'amount': row[2],
                    'currency': row[3],
                    'status': row[4],
                    'created_at': row[5]
                })
            
            conn.close()
        except Exception as e:
            logger.error(f"Error getting recent payments: {e}")
        
        context = {
            'tone_stats': tone_stats,
            'tone_bots': tone_bots,
            'recent_payments': recent_payments,
            'tone_available': TONE_AVAILABLE,
            'system': {
                'domain': settings.DOMAIN
            }
        }
        
        return render_template('tone_dashboard.html', **context)
    except Exception as e:
        logger.error(f"Error rendering tone dashboard: {e}")
        return f"Error loading tone dashboard: {str(e)}", 500

@app.route('/api/health')
def api_health():
    """API health check - always returns JSON"""
    return jsonify({
        "status": "healthy", 
        "service": "admin_dashboard",
        "timestamp": datetime.now().isoformat(),
        "tone_integration": TONE_AVAILABLE
    })

@app.route('/api/webhook_info')
def api_webhook_info():
    """מידע על webhooks - API version"""
    try:
        from core.bot_handler import find_tokens
        import requests
        
        tokens = find_tokens()
        results = {}
        
        for key, token in tokens:
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{token}/getWebhookInfo",
                    timeout=10
                )
                results[key] = {
                    'status_code': r.status_code,
                    'data': r.json() if r.status_code == 200 else {'error': r.text}
                }
            except Exception as e:
                results[key] = {'error': str(e)}
        
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error getting webhook info: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health_check')
def api_health_check():
    """בדיקת בריאות כל הבוטים - API version"""
    try:
        health_data = get_all_bots_health()
        return jsonify(health_data)
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tone_stats')
def api_tone_stats():
    """Get Tone statistics - API version"""
    try:
        tone_stats = get_tone_stats()
        return jsonify(tone_stats)
    except Exception as e:
        logger.error(f"Error getting tone stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/crypto_stats')
def api_crypto_stats():
    """Get cryptocurrency statistics - API version"""
    try:
        crypto_stats = get_crypto_stats()
        
        # Get token info safely
        try:
            from config.blockchain import blockchain_config
            token_price = blockchain_config.TOKEN_PRICE_USD
            token_symbol = blockchain_config.TOKEN_SYMBOL
            business_wallet = getattr(blockchain_config, 'BUSINESS_WALLET', 'Not set')
        except ImportError:
            token_price = 0.01
            token_symbol = "YTT"
            business_wallet = "Not set"
        
        return jsonify({
            'wallet_count': crypto_stats['crypto_wallet_count'],
            'transaction_count': crypto_stats['crypto_transaction_count'],
            'token_price': token_price,
            'token_symbol': token_symbol,
            'business_wallet': business_wallet
        })
    except Exception as e:
        logger.error(f"Error getting crypto stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/system_stats')
def api_system_stats():
    """Get system statistics - API version"""
    try:
        system_stats = get_system_stats()
        webhook_summary = get_webhook_summary()
        tone_stats = get_tone_stats()
        
        return jsonify({
            'system_stats': system_stats,
            'bot_count': len(webhook_summary),
            'tone_stats': tone_stats,
            'webhook_summary': webhook_summary
        })
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/approve', methods=['POST'])
def approve_request():
    """אישור בקשת משתמש"""
    try:
        entry_id = request.form.get('entry_id')
        if not entry_id:
            return jsonify({'error': 'Missing entry_id'}), 400
        
        success, message = admin_approve_request(entry_id, "web-dashboard")
        
        if success:
            return jsonify({'status': 'success', 'message': f'Request {entry_id} approved'})
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        logger.error(f"Error approving request: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/reject', methods=['POST'])
def reject_request():
    """דחיית בקשת משתמש"""
    try:
        entry_id = request.form.get('entry_id')
        reason = request.form.get('reason')
        
        if not entry_id or not reason:
            return jsonify({'error': 'Missing entry_id or reason'}), 400
        
        success, message = admin_reject_request(entry_id, reason, "web-dashboard")
        
        if success:
            return jsonify({'status': 'success', 'message': f'Request {entry_id} rejected'})
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        logger.error(f"Error rejecting request: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/generate_referral', methods=['POST'])
def generate_referral():
    """יצירת לינק הפניה"""
    try:
        env_key = request.form.get('env_key')
        user_id = request.form.get('user_id')
        
        if not env_key or not user_id:
            return jsonify({'error': 'Missing env_key or user_id'}), 400
        
        # Find the token for the selected bot
        from core.bot_handler import find_tokens
        tokens = find_tokens()
        
        token = None
        for key, t in tokens:
            if key == env_key:
                token = t
                break
        
        if not token:
            return jsonify({'error': 'Token not found for selected bot'}), 400
        
        referral_link = generate_referral_link_for_user(token, user_id)
        
        if referral_link:
            return jsonify({
                'status': 'success', 
                'referral_link': referral_link,
                'user_id': user_id,
                'bot': env_key
            })
        else:
            return jsonify({'error': 'Failed to generate referral link'}), 400
    except Exception as e:
        logger.error(f"Error generating referral: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/reset_webhooks', methods=['POST'])
def reset_webhooks():
    """איפוס webhooks"""
    try:
        from main import setup_webhooks
        setup_webhooks()
        return jsonify({'status': 'success', 'message': 'Webhooks reset initiated'})
    except Exception as e:
        logger.error(f"Error resetting webhooks: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Old routes for compatibility (return JSON instead of HTML)
@app.route('/webhook_info')
def webhook_info():
    return api_webhook_info()

@app.route('/health_check')
def health_check():
    return api_health_check()

@app.route('/crypto_stats')
def crypto_stats():
    return api_crypto_stats()

@app.route('/export/referrals.csv')
def export_referrals():
    """ייצוא הפניות ל-CSV"""
    try:
        data = load_referrals()
        
        output = io.StringIO()
        output.write("referrer_id,referred_id,bot,timestamp\n")
        
        for referrer_id, referrals in data.get('by_referrer', {}).items():
            for ref in referrals:
                output.write(f"{referrer_id},{ref['referred']},{ref['bot']},{ref['ts']}\n")
        
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=referrals.csv"}
        )
        
        return response
    except Exception as e:
        logger.error(f"Error exporting referrals: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/export/tone_payments.csv')
def export_tone_payments():
    """ייצוא תשלומי טון ל-CSV"""
    try:
        conn = sqlite3.connect('data/bot_data.db')
        cursor = conn.execute('''
            SELECT invoice_id, user_id, amount, currency, status, created_at 
            FROM tone_payments 
            ORDER BY created_at DESC
        ''')
        
        output = io.StringIO()
        output.write("invoice_id,user_id,amount,currency,status,created_at\n")
        
        for row in cursor:
            output.write(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]}\n")
        
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=tone_payments.csv"}
        )
        
        conn.close()
        return response
    except Exception as e:
        logger.error(f"Error exporting tone payments: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/export_wallets')
def export_wallets():
    """Export wallets to CSV"""
    try:
        if not os.path.exists('data/wallets.db'):
            return jsonify({'error': 'Wallets database not found'}), 404
            
        conn = sqlite3.connect('data/wallets.db')
        cursor = conn.execute('''
            SELECT user_id, address, balance_bnb, balance_tokens, bank_account, created_at 
            FROM user_wallets 
            ORDER BY created_at DESC
        ''')
        
        output = io.StringIO()
        output.write("user_id,address,balance_bnb,balance_tokens,bank_account,created_at\n")
        
        for row in cursor:
            output.write(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4] or ''},{row[5]}\n")
        
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=wallets.csv"}
        )
        
        conn.close()
        return response
    except Exception as e:
        logger.error(f"Error exporting wallets: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)

from flask import Flask, request, jsonify
import json
from core.bot_handler import handle_update, handle_callback_query

app = Flask(__name__)

# Store the tokens for each bot
from core.bot_handler import find_tokens
tokens_data = find_tokens()
tokens = [token for _, token in tokens_data]

@app.route('/bot<int:bot_id>', methods=['POST'])
def webhook_bot(bot_id):
    """Endpoint for webhook of each bot"""
    if bot_id < 1 or bot_id > len(tokens):
        return jsonify({"status": "error", "message": "Bot not found"}), 404
    
    bot_token = tokens[bot_id - 1]
    update = request.get_json()
    
    if not update:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    
    # Process the update
    result = handle_update(update, bot_token)
    return jsonify(result)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Generic webhook endpoint for default bot"""
    if not tokens:
        return jsonify({"status": "error", "message": "No bots configured"}), 500
    
    # Use the first bot as default
    bot_token = tokens[0]
    update = request.get_json()
    
    if not update:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    
    # Process the update
    result = handle_update(update, bot_token)
    return jsonify(result)

@app.route('/')
def index():
    return jsonify({"status": "active", "service": "Bot Factory Webhook"})

if __name__ == '__main__':
    app.run(port=5000)

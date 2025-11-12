# core/tone_integration.py
import requests
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Constants
TONE_AVAILABLE = True

class ToneAPI:
    def __init__(self):
        self.base_url = "https://api.ton.app/v1"  # להתאים לכתובת האמיתית של טון
        self.tokens = {
            'tone_bot_1': os.getenv('BOT6_TOKEN', '5ff1c8c048bb7f39b515ed354e638b1fe65f831243ab47d53096df0e1f8d8099'),
            'tone_bot_2': os.getenv('BOT7_TOKEN', '50e782e4efe6104c0821a4884412505972a23d14e7dc562030a3da8a41b6fd0f')
        }
    
    def send_message(self, bot_key, chat_id, text, **kwargs):
        """שליחת הודעה דרך API טון"""
        try:
            token = self.tokens.get(bot_key)
            if not token:
                return {'error': 'Token not found'}
            
            # כאן יש להתאים ל-API הספציפי של טון
            response = requests.post(
                f"{self.base_url}/sendMessage",
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json={
                    'chat_id': chat_id,
                    'text': text,
                    **kwargs
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Tone message sent to {chat_id}")
                return response.json()
            else:
                logger.error(f"Tone API error: {response.status_code} - {response.text}")
                return {'error': f'API error: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Tone API exception: {e}")
            return {'error': str(e)}
    
    def get_balance(self, bot_key):
        """קבלת יתרה/סטטוס מבוט טון"""
        try:
            token = self.tokens.get(bot_key)
            response = requests.get(
                f"{self.base_url}/getMe",
                headers={'Authorization': f'Bearer {token}'},
                timeout=10
            )
            return response.json() if response.status_code == 200 else {'error': 'Failed to get balance'}
        except Exception as e:
            return {'error': str(e)}
    
    def create_invoice(self, bot_key, amount, currency='USD', description='Payment'):
        """יצירת חשבונית/Invoice דרך טון"""
        try:
            token = self.tokens.get(bot_key)
            response = requests.post(
                f"{self.base_url}/createInvoice",
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                json={
                    'amount': amount,
                    'currency': currency,
                    'description': description,
                    'timestamp': datetime.now().isoformat()
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'API error: {response.status_code}'}
                
        except Exception as e:
            return {'error': str(e)}
    
    def get_nft_collection(self, bot_key, user_id):
        """קבלת אוסף NFT של משתמש"""
        try:
            token = self.tokens.get(bot_key)
            response = requests.get(
                f"{self.base_url}/nft/collection/{user_id}",
                headers={'Authorization': f'Bearer {token}'},
                timeout=10
            )
            return response.json() if response.status_code == 200 else {'error': 'Failed to get NFT collection'}
        except Exception as e:
            return {'error': str(e)}

# Instance גלובלית
tone_api = ToneAPI()

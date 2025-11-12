# utils/health_check.py
import requests
from core.bot_handler import find_tokens

def get_all_bots_health():
    """
    Check health of all bots by testing their webhook info
    Returns a dictionary with health status for each bot
    """
    tokens = find_tokens()
    health_data = {}
    
    for env_key, token in tokens:
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
                    'status': 'healthy',
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

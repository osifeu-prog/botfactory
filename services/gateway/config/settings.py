import os

class Settings:
    # Domain and server settings
    DOMAIN = os.getenv('RAILWAY_STATIC_URL', 'https://botfactory-production.up.railway.app')
    
    # Telegram settings
    ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '')
    
    # Request settings
    REQUEST_TIMEOUT = 30
    
    # Database settings
    DATABASE_PATH = 'data/bot_data.db'

settings = Settings()

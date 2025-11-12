# config/ton_settings.py
class TONSettings:
    # TON Network Settings
    TON_NETWORK = "testnet"  # "mainnet" or "testnet"
    
    # Your TON Coin/Jetton contract address
    JETTON_CONTRACT_ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c"  # Replace with your actual contract
    
    # Wallet settings
    DEFAULT_WALLET_VERSION = "v4r2"
    
    # Gas limits
    DEPLOY_GAS_LIMIT = 0.05  # TON
    TRANSFER_GAS_LIMIT = 0.01  # TON
    
    # API settings
    TONCENTER_TIMEOUT = 30
    MAX_RETRIES = 3
    
    # Bot settings
    DEFAULT_LANGUAGE = "hebrew"
    SUPPORTED_CURRENCIES = ["TON", "USD", "EUR"]
    
    # Transaction settings
    MIN_DEPOSIT_AMOUNT = 0.1  # TON
    MAX_WITHDRAWAL_AMOUNT = 1000  # TON
    DAILY_LIMIT = 10000  # TON

ton_settings = TONSettings()

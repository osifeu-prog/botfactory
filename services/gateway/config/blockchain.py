# config/blockchain.py
import os

class BlockchainConfig:
    # Binance Smart Chain Configuration
    BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
    CHAIN_ID = 56
    SYMBOL = "BNB"
    EXPLORER_URL = "https://bscscan.com"
    
    # Token Contract Address
    TOKEN_CONTRACT = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
    
    # Wallet Configuration
    WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "")  # For business operations
    BUSINESS_WALLET = os.getenv("BUSINESS_WALLET", "")  # Main business wallet address
    
    # Token Details
    TOKEN_NAME = "YourToken"
    TOKEN_SYMBOL = "YTT"
    TOKEN_DECIMALS = 18
    
    # Exchange Rates
    TOKEN_PRICE_USD = 0.01
    MIN_PURCHASE_BNB = 0.001
    MAX_PURCHASE_BNB = 10.0

# Initialize Web3 only if RPC URL is available
w3 = None
try:
    if BlockchainConfig.BSC_RPC_URL:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(BlockchainConfig.BSC_RPC_URL))
        if w3.is_connected():
            print(f"✅ Connected to BSC - Chain ID: {w3.eth.chain_id}")
        else:
            print("❌ Failed to connect to BSC")
            w3 = None
except ImportError:
    print("❌ Web3 not installed - blockchain features disabled")
    w3 = None
except Exception as e:
    print(f"❌ BSC connection error: {e}")
    w3 = None

blockchain_config = BlockchainConfig()

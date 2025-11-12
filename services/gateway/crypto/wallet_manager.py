# crypto/wallet_manager.py
import os
import json
import sqlite3
import secrets
from datetime import datetime
import requests

# Try to import Web3, but make it optional
HAS_WEB3 = False
w3 = None
try:
    from web3 import Web3
    from eth_account import Account
    HAS_WEB3 = True
    print("✅ Web3 loaded successfully")
except ImportError as e:
    print(f"❌ Web3 import failed: {e}")

from config.blockchain import blockchain_config

class WalletManager:
    def __init__(self):
        self.w3 = None
        self.contract_address = blockchain_config.TOKEN_CONTRACT
        self.init_database()
        self.token_contract = None
        
        # Initialize Web3 if available
        if HAS_WEB3 and blockchain_config.BSC_RPC_URL:
            try:
                self.w3 = Web3(Web3.HTTPProvider(blockchain_config.BSC_RPC_URL))
                if self.w3.is_connected():
                    print("✅ Connected to BSC via Web3")
                    self.token_contract = self.load_token_contract()
                else:
                    print("❌ Failed to connect to BSC")
                    self.w3 = None
            except Exception as e:
                print(f"❌ Web3 initialization failed: {e}")
                self.w3 = None
    
    def init_database(self):
        """Initialize database for wallet storage"""
        os.makedirs('data', exist_ok=True)
        conn = sqlite3.connect('data/wallets.db')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_wallets (
                user_id INTEGER PRIMARY KEY,
                address TEXT NOT NULL,
                private_key_encrypted TEXT NOT NULL,
                created_at TEXT NOT NULL,
                balance_bnb REAL DEFAULT 0,
                balance_tokens REAL DEFAULT 0,
                bank_account TEXT,
                bank_verified INTEGER DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tx_hash TEXT,
                tx_type TEXT,
                amount REAL,
                currency TEXT,
                status TEXT,
                created_at TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def load_token_contract(self):
        """Load token contract ABI"""
        if not self.w3 or not self.contract_address:
            return None
        
        try:
            # Minimal ERC-20 ABI for balance checks and transfers
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "symbol",
                    "outputs": [{"name": "", "type": "string"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "name",
                    "outputs": [{"name": "", "type": "string"}],
                    "type": "function"
                },
                {
                    "constant": False,
                    "inputs": [
                        {"name": "_to", "type": "address"},
                        {"name": "_value", "type": "uint256"}
                    ],
                    "name": "transfer",
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function"
                }
            ]
            
            return self.w3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=erc20_abi
            )
        except Exception as e:
            print(f"❌ Error loading token contract: {e}")
            return None
    
    def create_wallet(self, user_id):
        """Create new wallet for user"""
        try:
            if not HAS_WEB3:
                return {'success': False, 'error': 'Blockchain features not available'}
                
            # Generate new account
            private_key = "0x" + secrets.token_hex(32)
            account = Account.from_key(private_key)
            
            # Simple encryption (in production use proper encryption)
            encrypted_pk = private_key  # For demo purposes
            
            # Store in database
            conn = sqlite3.connect('data/wallets.db')
            conn.execute('''
                INSERT OR REPLACE INTO user_wallets 
                (user_id, address, private_key_encrypted, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, account.address, encrypted_pk, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'address': account.address
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_wallet(self, user_id):
        """Get user wallet info"""
        try:
            conn = sqlite3.connect('data/wallets.db')
            cursor = conn.execute(
                'SELECT * FROM user_wallets WHERE user_id = ?', 
                (user_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'user_id': row[0],
                    'address': row[1],
                    'balance_bnb': row[4] or 0,
                    'balance_tokens': row[5] or 0,
                    'bank_account': row[6],
                    'bank_verified': bool(row[7])
                }
            return None
        except Exception as e:
            print(f"Error getting wallet: {e}")
            return None
    
    def get_balances(self, user_id):
        """Get real-time balances from blockchain"""
        wallet = self.get_wallet(user_id)
        if not wallet:
            return wallet
        
        try:
            # If Web3 is available, get real balances
            if self.w3:
                # Get BNB balance
                balance_wei = self.w3.eth.get_balance(Web3.to_checksum_address(wallet['address']))
                wallet['balance_bnb'] = float(self.w3.from_wei(balance_wei, 'ether'))
                
                # Get token balance
                if self.token_contract:
                    try:
                        token_balance = self.token_contract.functions.balanceOf(
                            Web3.to_checksum_address(wallet['address'])
                        ).call()
                        wallet['balance_tokens'] = token_balance / (10 ** 18)
                    except Exception as e:
                        print(f"Error getting token balance: {e}")
                        wallet['balance_tokens'] = 0
                
                # Update database
                conn = sqlite3.connect('data/wallets.db')
                conn.execute('''
                    UPDATE user_wallets SET balance_bnb = ?, balance_tokens = ? 
                    WHERE user_id = ?
                ''', (wallet['balance_bnb'], wallet['balance_tokens'], user_id))
                conn.commit()
                conn.close()
            
            return wallet
        except Exception as e:
            print(f"Error getting balances: {e}")
            return wallet
    
    def set_bank_account(self, user_id, bank_account):
        """Set user bank account for withdrawals"""
        try:
            conn = sqlite3.connect('data/wallets.db')
            conn.execute('''
                UPDATE user_wallets SET bank_account = ?, bank_verified = 0 
                WHERE user_id = ?
            ''', (bank_account, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error setting bank account: {e}")
            return False
    
    def get_token_price(self):
        """Get current token price in BNB"""
        return blockchain_config.TOKEN_PRICE_USD
    
    def calculate_tokens_for_bnb(self, bnb_amount):
        """Calculate how many tokens user gets for BNB amount"""
        token_price = self.get_token_price()
        return bnb_amount / token_price
    
    def create_purchase_order(self, user_id, bnb_amount):
        """Create purchase order for tokens"""
        try:
            wallet = self.get_wallet(user_id)
            if not wallet:
                return {'success': False, 'error': 'Wallet not found'}
            
            tokens_amount = self.calculate_tokens_for_bnb(bnb_amount)
            
            conn = sqlite3.connect('data/wallets.db')
            cursor = conn.execute('''
                INSERT INTO transactions 
                (user_id, tx_type, amount, currency, status, created_at)
                VALUES (?, 'purchase', ?, 'BNB', 'pending', ?)
            ''', (user_id, bnb_amount, datetime.now().isoformat()))
            
            tx_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            business_wallet = blockchain_config.BUSINESS_WALLET or "SET_BUSINESS_WALLET_IN_ENV"
            
            return {
                'success': True,
                'order_id': tx_id,
                'bnb_amount': bnb_amount,
                'token_amount': tokens_amount,
                'business_wallet': business_wallet
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def confirm_purchase(self, order_id, tx_hash):
        """Confirm purchase with transaction hash"""
        try:
            conn = sqlite3.connect('data/wallets.db')
            cursor = conn.execute(
                'SELECT * FROM transactions WHERE id = ?', 
                (order_id,)
            )
            order = cursor.fetchone()
            
            if order:
                conn.execute('''
                    UPDATE transactions SET tx_hash = ?, status = 'completed' 
                    WHERE id = ?
                ''', (tx_hash, order_id))
                conn.commit()
            
            conn.close()
            return True
        except Exception as e:
            print(f"Error confirming purchase: {e}")
            return False
    
    def get_transaction_history(self, user_id, limit=10):
        """Get user transaction history"""
        try:
            conn = sqlite3.connect('data/wallets.db')
            cursor = conn.execute('''
                SELECT * FROM transactions 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            transactions = []
            for row in cursor.fetchall():
                transactions.append({
                    'id': row[0],
                    'tx_hash': row[2],
                    'type': row[3],
                    'amount': row[4],
                    'currency': row[5],
                    'status': row[6],
                    'date': row[7]
                })
            
            conn.close()
            return transactions
        except Exception as e:
            print(f"Error getting transaction history: {e}")
            return []

# Global wallet manager instance
wallet_manager = WalletManager()

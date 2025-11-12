# crypto/trading_handler.py
import os
import json
from datetime import datetime

class TradingHandler:
    def __init__(self):
        self.wallet_manager = None
        self.blockchain_config = None
        self._initialize_dependencies()
    
    def _initialize_dependencies(self):
        """Initialize dependencies lazily to avoid circular imports"""
        try:
            from crypto.wallet_manager import wallet_manager
            from config.blockchain import blockchain_config
            self.wallet_manager = wallet_manager
            self.blockchain_config = blockchain_config
        except ImportError as e:
            print(f"❌ Failed to initialize crypto dependencies: {e}")
            # Create fallback config
            class FallbackConfig:
                TOKEN_SYMBOL = "YTT"
                TOKEN_PRICE_USD = 0.01
                MIN_PURCHASE_BNB = 0.001
                MAX_PURCHASE_BNB = 10.0
                TOKEN_CONTRACT = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
            self.blockchain_config = FallbackConfig()
    
    def handle_crypto_command(self, user_id, command, args=None):
        """Handle all crypto-related commands"""
        if not self.wallet_manager or not self.blockchain_config:
            return {
                'success': False, 
                'message': '❌ מערכת הקריפטו אינה זמינה כרגע. אנא נסה שוב מאוחר יותר.'
            }
            
        if command == 'create_wallet':
            return self._create_wallet(user_id)
        elif command == 'balance':
            return self._get_balance(user_id)
        elif command == 'buy':
            return self._buy_tokens(user_id, args)
        elif command == 'sell':
            return self._sell_tokens(user_id, args)
        elif command == 'set_bank':
            return self._set_bank_account(user_id, args)
        elif command == 'history':
            return self._get_history(user_id)
        elif command == 'price':
            return self._get_price()
        elif command == 'help':
            return self._get_help()
        else:
            return self._get_help()
    
    def _create_wallet(self, user_id):
        """Create wallet for user"""
        result = self.wallet_manager.create_wallet(user_id)
        if result['success']:
            wallet_info = f"""
🎉 **ארנק נוצר בהצלחה!**

**כתובת הארנק:** `{result['address']}`
**רשת:** BSC (Binance Smart Chain)

💡 **הערות חשובות:**
• שמור את המפתח הפרטי במקום בטוח
• שלח רק BNB לרשת BSC
• המטבע שלנו: {self.blockchain_config.TOKEN_SYMBOL}

השתמש בפקודות:
/balance - צפה ביתרות
/buy - רכישת מטבעות
/price - מחיר עדכני
"""
            return {'success': True, 'message': wallet_info}
        else:
            error_msg = result.get('error', 'Unknown error')
            return {'success': False, 'message': f'❌ שגיאה ביצירת הארנק: {error_msg}'}
    
    def _get_balance(self, user_id):
        """Get user balances"""
        wallet = self.wallet_manager.get_balances(user_id)
        if not wallet:
            return {
                'success': False, 
                'message': '❌ לא נמצא ארנק. השתמש ב-/create_wallet ליצירת ארנק.'
            }
        
        balance_info = f"""
💰 **יתרות שלך:**

**BNB:** {wallet['balance_bnb']:.6f}
**{self.blockchain_config.TOKEN_SYMBOL}:** {wallet['balance_tokens']:.2f}

**כתובת ארנק:** `{wallet['address']}`
"""
        if wallet['bank_account']:
            verified = "✅ מאומת" if wallet['bank_verified'] else "⏳ ממתין לאימות"
            balance_info += f"\n**חשבון בנק:** {wallet['bank_account']} ({verified})"
        
        return {'success': True, 'message': balance_info}
    
    def _buy_tokens(self, user_id, amount_str):
        """Handle token purchase"""
        if not amount_str:
            return {
                'success': False,
                'message': '❌ אנא specify amount. Example: /buy 0.1'
            }
        
        try:
            bnb_amount = float(amount_str)
            min_purchase = self.blockchain_config.MIN_PURCHASE_BNB
            max_purchase = self.blockchain_config.MAX_PURCHASE_BNB
            
            if bnb_amount < min_purchase:
                return {
                    'success': False,
                    'message': f'❌ סכום מינימלי: {min_purchase} BNB'
                }
            if bnb_amount > max_purchase:
                return {
                    'success': False,
                    'message': f'❌ סכום מקסימלי: {max_purchase} BNB'
                }
            
            result = self.wallet_manager.create_purchase_order(user_id, bnb_amount)
            if result['success']:
                business_wallet = result.get('business_wallet', 'SET_BUSINESS_WALLET_IN_ENV')
                message = f"""
🛒 **הזמנת רכישה נוצרה!**

**סכום BNB:** {bnb_amount}
**מקבל:** {result['token_amount']:.2f} {self.blockchain_config.TOKEN_SYMBOL}
**מחיר:** ${self.blockchain_config.TOKEN_PRICE_USD} per token

**שלח את ה-BNB לכתובת:**
`{business_wallet}`

**רשת:** BSC (Binance Smart Chain)

**לאחר ההעברה, שלח את hash העסקה עם הפקודה:**
/confirm {result['order_id']} <TX_HASH>
"""
                return {'success': True, 'message': message}
            else:
                error_msg = result.get('error', 'Unknown error')
                return {'success': False, 'message': f'❌ שגיאה ביצירת ההזמנה: {error_msg}'}
        
        except ValueError:
            return {'success': False, 'message': '❌ סכום לא תקין'}
    
    def _sell_tokens(self, user_id, amount_str):
        """Handle token sale"""
        if not amount_str:
            return {
                'success': False,
                'message': '❌ אנא specify amount. Example: /sell 100'
            }
        
        try:
            token_amount = float(amount_str)
            wallet = self.wallet_manager.get_balances(user_id)
            
            if not wallet:
                return {
                    'success': False,
                    'message': '❌ לא נמצא ארנק. צור ארנק תחילה.'
                }
            
            if token_amount > wallet['balance_tokens']:
                return {
                    'success': False,
                    'message': f'❌ יתרה לא מספיקה. יש לך {wallet["balance_tokens"]:.2f} tokens'
                }
            
            # Calculate BNB value
            bnb_value = token_amount * self.blockchain_config.TOKEN_PRICE_USD
            
            message = f"""
💰 **בקשת מכירה**

**מכירה:** {token_amount:.2f} {self.blockchain_config.TOKEN_SYMBOL}
**יקבל:** {bnb_value:.4f} BNB

**לאשר מכירה?**
"""
            return {
                'success': True, 
                'message': message,
                'requires_confirmation': True,
                'action': 'sell',
                'amount': token_amount
            }
        
        except ValueError:
            return {'success': False, 'message': '❌ סכום לא תקין'}
    
    def _set_bank_account(self, user_id, account_info):
        """Set bank account for withdrawals"""
        if not account_info:
            return {
                'success': False,
                'message': '❌ אנא provide bank account details'
            }
        
        success = self.wallet_manager.set_bank_account(user_id, account_info)
        if success:
            return {
                'success': True,
                'message': '✅ פרטי הבנק נשמרו וממתינים לאימות'
            }
        else:
            return {
                'success': False,
                'message': '❌ שגיאה בשמירת פרטי הבנק'
            }
    
    def _get_history(self, user_id):
        """Get transaction history"""
        transactions = self.wallet_manager.get_transaction_history(user_id)
        
        if not transactions:
            return {
                'success': True,
                'message': '📝 אין עדיין היסטוריית עסקאות'
            }
        
        history_text = "📊 **היסטוריית עסקאות:**\n\n"
        for tx in transactions:
            status_icon = "✅" if tx['status'] == 'completed' else "⏳"
            history_text += f"{status_icon} {tx['type']} - {tx['amount']} {tx['currency']}\n"
            history_text += f"📅 {tx['date'][:16]}\n\n"
        
        return {'success': True, 'message': history_text}
    
    def _get_price(self):
        """Get current token price"""
        price_info = f"""
💹 **מחיר עדכני:**

**מטבע:** {self.blockchain_config.TOKEN_SYMBOL}
**מחיר:** ${self.blockchain_config.TOKEN_PRICE_USD}
**רשת:** BSC

**חוזה:** `{self.blockchain_config.TOKEN_CONTRACT}`

**קנה עכשיו עם:** /buy
"""
        return {'success': True, 'message': price_info}
    
    def _get_help(self):
        """Get crypto help"""
        help_text = f"""
💰 **פקודות קריפטו:**

/create_wallet - צור ארנק חדש
/balance - צפה ביתרות
/price - מחיר {self.blockchain_config.TOKEN_SYMBOL} עדכני
/buy [amount] - רכישת מטבעות ב-BNB
/sell [amount] - מכירת מטבעות
/set_bank [details] - הגדר חשבון בנק
/history - היסטוריית עסקאות

**רשת:** BSC (Binance Smart Chain)
**מטבע:** {self.blockchain_config.TOKEN_SYMBOL}
"""
        return {'success': True, 'message': help_text}

# Global trading handler instance
trading_handler = TradingHandler()

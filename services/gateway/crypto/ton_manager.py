# crypto/ton_manager.py
import asyncio
import aiohttp
import json
import base58
from typing import Dict, Optional, List
from config.settings import settings

class TONManager:
    def __init__(self):
        self.testnet_api_key = "50e782e4efe6104c0821a4884412505972a23d14e7dc562030a3da8a41b6fd0f"
        self.mainnet_api_key = "5ff1c8c048bb7f39b515ed354e638b1fe65f831243ab47d53096df0e1f8d8099"
        self.base_url_testnet = "https://testnet.toncenter.com/api/v2"
        self.base_url_mainnet = "https://toncenter.com/api/v2"
        self.headers = {
            'Content-Type': 'application/json'
        }

    def get_base_url(self, testnet=True):
        return self.base_url_testnet if testnet else self.base_url_mainnet

    def get_api_key(self, testnet=True):
        return self.testnet_api_key if testnet else self.mainnet_api_key

    async def make_request(self, method: str, params: Dict = None, testnet: bool = True):
        url = self.get_base_url(testnet)
        api_key = self.get_api_key(testnet)
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    json=payload, 
                    headers={**self.headers, 'X-API-Key': api_key},
                    timeout=30
                ) as response:
                    result = await response.json()
                    return result
        except Exception as e:
            print(f"TON API Error: {e}")
            return None

    async def get_wallet_balance(self, address: str, testnet: bool = True) -> Optional[float]:
        """Get balance of wallet in TON"""
        result = await self.make_request("getAddressBalance", {"address": address}, testnet)
        if result and 'result' in result:
            # Convert from nanoton to TON
            balance_nano = int(result['result'])
            return balance_nano / 1e9
        return None

    async def get_token_balance(self, wallet_address: str, token_address: str, testnet: bool = True):
        """Get balance of jetton (token) in wallet"""
        method = "runGetMethod"
        params = {
            "address": token_address,
            "method": "get_wallet_data",
            "stack": []
        }
        
        result = await self.make_request(method, params, testnet)
        if result and 'result' in result:
            return result
        return None

    async def send_ton(self, from_address: str, to_address: str, amount: float, secret_key: str, testnet: bool = True):
        """Send TON coins"""
        amount_nano = int(amount * 1e9)
        
        # This is a simplified version - in production you'd use tonlib or other SDK
        params = {
            "from": from_address,
            "to": to_address,
            "amount": amount_nano,
            "secretKey": secret_key
        }
        
        result = await self.make_request("sendTransaction", params, testnet)
        return result

    async def create_wallet(self, testnet: bool = True):
        """Generate new TON wallet"""
        # This would integrate with ton-crypto or tonlib to generate keys
        # For now, return mock data
        return {
            "address": "EQXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" + ("test" if testnet else "main"),
            "public_key": "pub_key_here",
            "secret_key": "secret_key_here"
        }

    async def get_transactions(self, address: str, limit: int = 10, testnet: bool = True):
        """Get transaction history for address"""
        result = await self.make_request("getTransactions", {
            "address": address,
            "limit": limit
        }, testnet)
        return result

    async def get_token_info(self, token_address: str, testnet: bool = True):
        """Get jetton token information"""
        result = await self.make_request("getJettonInfo", {
            "address": token_address
        }, testnet)
        return result

    def validate_address(self, address: str) -> bool:
        """Validate TON address format"""
        try:
            if address.startswith('EQ') or address.startswith('kQ'):
                # Basic length validation
                return len(address) >= 48
            return False
        except:
            return False

    async def get_gas_price(self, testnet: bool = True):
        """Get current gas prices"""
        result = await self.make_request("getGasPrice", {}, testnet)
        return result

# Singleton instance
ton_manager = TONManager()

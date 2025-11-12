import base64
import json
import os
import time
from typing import Optional

from web3 import Web3
from web3.exceptions import TransactionNotFound


ONCHAIN_MODE = os.getenv("ONCHAIN_MODE", "SIMULATED").upper()
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "")
BSC_CHAIN_ID = int(os.getenv("BSC_CHAIN_ID", "97"))  # testnet by default
BSC_GAS_LIMIT = int(os.getenv("BSC_GAS_LIMIT", "21000"))
BSC_GAS_PRICE_GWEI = int(os.getenv("BSC_GAS_PRICE_GWEI", "1"))


def _get_web3() -> Web3:
    if not BSC_RPC_URL:
        raise RuntimeError("BSC_RPC_URL not configured")
    w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
    if not w3.is_connected():
        raise RuntimeError("Cannot connect to BSC RPC")
    return w3


def make_transfer_build_boc_only(
    wallet_address: str,
    privkey_hex: str,
    dest_address: str,
    amount_nano: int,
    comment: Optional[str] = None,
) -> str:
    """במצב SIMULATED – בונה payload JSON מקודד base64.
    במצב BSC – גם יחזיר payload תיאורי של הטרנזקציה שתישלח.
    """
    payload = {
        "mode": ONCHAIN_MODE,
        "from": wallet_address,
        "to": dest_address,
        "amount_nano": int(amount_nano),
        "comment": comment,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def send_boc_via_toncenter(boc_base64: str, privkey_hex: str) -> dict:
    """שם היסטורי. בפועל:
    - SIMULATED: מחזיר אובייקט דמו.
    - BSC: מבצע טרנזקציית native transfer אמיתית דרך web3 ומשתמש ב-privkey_hex.
    """
    try:
        raw = base64.b64decode(boc_base64.encode("utf-8"))
        decoded = json.loads(raw.decode("utf-8"))
    except Exception:
        decoded = None

    if ONCHAIN_MODE != "BSC":
        return {
            "ok": True,
            "network": "SIMULATED",
            "boc_base64": boc_base64,
            "decoded": decoded,
            "tx_hash": "sim_" + hex(int(time.time()))[2:],
            "timestamp": int(time.time()),
        }

    w3 = _get_web3()
    account = w3.eth.account.from_key(privkey_hex)
    dest = Web3.to_checksum_address(decoded["to"])

    value_wei = int(decoded["amount_nano"])

    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.to_wei(BSC_GAS_PRICE_GWEI, "gwei")

    tx = {
        "nonce": nonce,
        "to": dest,
        "value": value_wei,
        "gas": BSC_GAS_LIMIT,
        "gasPrice": gas_price,
        "chainId": BSC_CHAIN_ID,
    }

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hash_hex = tx_hash.hex()

    return {
        "ok": True,
        "network": "BSC",
        "boc_base64": boc_base64,
        "decoded": decoded,
        "tx_hash": tx_hash_hex,
        "from": account.address,
        "to": dest,
        "value_wei": value_wei,
        "gas_limit": BSC_GAS_LIMIT,
        "gas_price_gwei": BSC_GAS_PRICE_GWEI,
        "timestamp": int(time.time()),
    }


def get_tx_status(tx_hash: str) -> dict:
    """בודק סטטוס טרנזקציה ברשת BSC.
    במצב SIMULATED מחזיר תשובה דמו בלבד.
    """
    if ONCHAIN_MODE != "BSC":
        return {
            "mode": "SIMULATED",
            "tx_hash": tx_hash,
            "status": "unknown (simulated)",
        }

    w3 = _get_web3()
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except TransactionNotFound:
        return {
            "mode": "BSC",
            "tx_hash": tx_hash,
            "found": False,
            "status": "pending_or_not_found",
        }

    status = "success" if receipt.status == 1 else "failed"
    return {
        "mode": "BSC",
        "tx_hash": tx_hash,
        "found": True,
        "status": status,
        "block_number": receipt.block_number,
        "gas_used": receipt.gas_used,
    }

import base64
from hashlib import sha256
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes


def _derive_key(master_password: str) -> bytes:
    if not master_password:
        raise ValueError("WALLET_MASTER_KEY is empty - cannot derive encryption key")
    return sha256(master_password.encode("utf-8")).digest()


def encrypt_private_key(privkey_hex: str, master_password: str) -> bytes:
    priv_bytes = bytes.fromhex(privkey_hex)
    key = _derive_key(master_password)
    iv = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(priv_bytes)
    payload = iv + tag + ciphertext
    return base64.b64encode(payload)


def decrypt_private_key(enc_payload_b64: bytes, master_password: str) -> str:
    if isinstance(enc_payload_b64, str):
        enc_payload_b64 = enc_payload_b64.encode("utf-8")
    raw = base64.b64decode(enc_payload_b64)
    iv = raw[:12]
    tag = raw[12:28]
    ciphertext = raw[28:]
    key = _derive_key(master_password)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    priv_bytes = cipher.decrypt_and_verify(ciphertext, tag)
    return priv_bytes.hex()


def generate_wallet_from_privkey(privkey_hex: str) -> dict:
    priv_bytes = bytes.fromhex(privkey_hex)
    pubkey = sha256(priv_bytes).hexdigest()
    addr_hash = sha256(pubkey.encode("utf-8")).hexdigest()
    address = "EQ" + addr_hash[:46]
    return {"address": address, "pubkey": pubkey}

import os, json, base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _aes():
    return AESGCM(base64.urlsafe_b64decode(os.environ["ENCRYPTION_KEY"]))


def encrypt(obj) -> str:
    nonce = os.urandom(12)
    ct = _aes().encrypt(nonce, json.dumps(obj).encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(text: str):
    raw = base64.b64decode(text)
    return json.loads(_aes().decrypt(raw[:12], raw[12:], None))
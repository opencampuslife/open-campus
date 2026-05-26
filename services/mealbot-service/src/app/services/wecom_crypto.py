from __future__ import annotations

import base64
import hashlib
import hmac
import shutil
import struct
import subprocess


class WeComCryptoError(ValueError):
    pass


def verify_signature(
    *,
    token: str,
    timestamp: str,
    nonce: str,
    encrypted: str,
    msg_signature: str,
) -> None:
    if not all((token, timestamp, nonce, encrypted, msg_signature)):
        raise WeComCryptoError("MISSING_SIGNATURE_FIELDS")
    raw = "".join(sorted([token, timestamp, nonce, encrypted]))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(digest, msg_signature):
        raise WeComCryptoError("INVALID_SIGNATURE")


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise WeComCryptoError("INVALID_PADDING")
    pad = data[-1]
    if pad < 1 or pad > 32 or len(data) < pad:
        raise WeComCryptoError("INVALID_PADDING")
    if not hmac.compare_digest(data[-pad:], bytes([pad]) * pad):
        raise WeComCryptoError("INVALID_PADDING")
    return data[:-pad]


def _decrypt_aes_cbc(ciphertext: bytes, aes_key: bytes) -> bytes:
    try:
        from Crypto.Cipher import AES  # type: ignore[import-not-found]

        return AES.new(aes_key, AES.MODE_CBC, aes_key[:16]).decrypt(ciphertext)
    except ImportError:
        openssl = shutil.which("openssl")
        if not openssl:
            raise WeComCryptoError("AES_BACKEND_UNAVAILABLE") from None
        proc = subprocess.run(
            [
                openssl,
                "enc",
                "-d",
                "-aes-256-cbc",
                "-K",
                aes_key.hex(),
                "-iv",
                aes_key[:16].hex(),
                "-nopad",
            ],
            input=ciphertext,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise WeComCryptoError("DECRYPT_FAILED")
        return proc.stdout


def decrypt_message(*, encrypted: str, encoding_aes_key: str, corp_id: str) -> str:
    try:
        aes_key = base64.b64decode(encoding_aes_key + "=")
        ciphertext = base64.b64decode(encrypted)
    except Exception as exc:
        raise WeComCryptoError("INVALID_BASE64") from exc
    if len(aes_key) != 32 or len(ciphertext) % 16 != 0:
        raise WeComCryptoError("INVALID_CIPHERTEXT")

    plain = _pkcs7_unpad(_decrypt_aes_cbc(ciphertext, aes_key))
    if len(plain) < 20:
        raise WeComCryptoError("INVALID_MESSAGE")
    msg_len = struct.unpack("!I", plain[16:20])[0]
    msg_end = 20 + msg_len
    if msg_end > len(plain):
        raise WeComCryptoError("INVALID_MESSAGE")
    msg = plain[20:msg_end]
    received_corp_id = plain[msg_end:].decode("utf-8")
    if not hmac.compare_digest(received_corp_id, corp_id):
        raise WeComCryptoError("INVALID_CORP_ID")
    return msg.decode("utf-8")

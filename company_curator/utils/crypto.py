"""Fernet symmetric encryption for sensitive data at rest.

SRP: Only responsible for encrypting/decrypting strings.
"""

from __future__ import annotations

from cryptography.fernet import Fernet


def generate_fernet_key() -> str:
    """Generate a new Fernet key (base64-encoded)."""
    return Fernet.generate_key().decode()


def encrypt(plaintext: str, key: str) -> str:
    """Encrypt a string using Fernet. Returns base64-encoded ciphertext."""
    f = Fernet(key.encode())
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str, key: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    f = Fernet(key.encode())
    return f.decrypt(ciphertext.encode()).decode()

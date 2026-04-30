"""Tests for encryption utilities."""

from company_curator.utils.crypto import decrypt, encrypt, generate_fernet_key


def test_encrypt_decrypt_roundtrip():
    key = generate_fernet_key()
    plaintext = "my-smtp-password"

    ciphertext = encrypt(plaintext, key)
    assert ciphertext != plaintext

    result = decrypt(ciphertext, key)
    assert result == plaintext


def test_different_keys_fail():
    key1 = generate_fernet_key()
    key2 = generate_fernet_key()

    ciphertext = encrypt("secret", key1)

    import pytest
    with pytest.raises(Exception):
        decrypt(ciphertext, key2)

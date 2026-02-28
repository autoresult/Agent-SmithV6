"""
Unit tests for EncryptionService — Encrypt/Decrypt API keys.

Testa round-trip, empty values, e erros de decryption.
Usa cryptography Fernet real (é lógica pura, não precisa de mock).
"""

import base64
import secrets

import pytest

from app.services.encryption_service import EncryptionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def encryption_service():
    """EncryptionService com chave válida."""
    # Gera uma chave Fernet válida (32 bytes base64-encoded)
    key_bytes = secrets.token_bytes(32)
    valid_key = base64.b64encode(key_bytes).decode("utf-8")

    # Override settings para usar chave de teste  
    from app.services import encryption_service as enc_mod
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(enc_mod.settings, "ENCRYPTION_KEY", valid_key)
        service = EncryptionService()
        yield service


# ═══════════════════════════════════════════════════════════════════════════
# ENCRYPT / DECRYPT ROUNDTRIP
# ═══════════════════════════════════════════════════════════════════════════


class TestEncryptDecryptRoundtrip:

    def test_roundtrip_simple_text(self, encryption_service):
        original = "sk-test-api-key-12345"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_roundtrip_unicode_text(self, encryption_service):
        original = "chave-com-acentuação-café-ñ"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_roundtrip_special_characters(self, encryption_service):
        original = "sk-proj-abc123!@#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_roundtrip_long_text(self, encryption_service):
        original = "x" * 10000
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_encrypted_differs_from_original(self, encryption_service):
        original = "my-secret-api-key"
        encrypted = encryption_service.encrypt(original)
        assert encrypted != original

    def test_different_encryptions_produce_different_output(self, encryption_service):
        """Fernet usa timestamp + IV, então cada encrypt é único."""
        original = "my-secret-api-key"
        enc1 = encryption_service.encrypt(original)
        enc2 = encryption_service.encrypt(original)
        assert enc1 != enc2  # Fernet includes timestamp and random IV


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════


class TestValidation:

    def test_encrypt_empty_string_raises(self, encryption_service):
        with pytest.raises(ValueError, match="plaintext cannot be empty"):
            encryption_service.encrypt("")

    def test_decrypt_empty_string_raises(self, encryption_service):
        with pytest.raises(ValueError, match="ciphertext cannot be empty"):
            encryption_service.decrypt("")


# ═══════════════════════════════════════════════════════════════════════════
# DECRYPTION ERRORS
# ═══════════════════════════════════════════════════════════════════════════


class TestDecryptionErrors:

    def test_decrypt_corrupted_data_raises(self, encryption_service):
        """Dados corrompidos devem levantar ValueError."""
        corrupted = base64.b64encode(b"this-is-not-encrypted").decode("utf-8")
        with pytest.raises(ValueError, match="Failed to decrypt"):
            encryption_service.decrypt(corrupted)

    def test_decrypt_invalid_base64_raises(self, encryption_service):
        """Base64 inválido deve levantar ValueError."""
        with pytest.raises((ValueError, Exception)):
            encryption_service.decrypt("not-valid-base64!!!")


# ═══════════════════════════════════════════════════════════════════════════
# KEY INITIALIZATION ERRORS
# ═══════════════════════════════════════════════════════════════════════════


class TestKeyInitialization:

    def test_empty_key_raises_value_error(self):
        from app.services import encryption_service as enc_mod
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(enc_mod.settings, "ENCRYPTION_KEY", "")
            with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
                EncryptionService()

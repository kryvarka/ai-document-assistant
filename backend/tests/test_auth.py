import jwt
import pytest

from src.config import settings
from src.utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestAuth:
    def test_create_and_decode_access_token(self):
        token = create_access_token(
            user_id="usr_test_1",
            email="user1@docqa.ai",
            role="Researcher",
        )
        assert isinstance(token, str)
        assert len(token) > 20

        payload = decode_access_token(token)
        assert payload["sub"] == "usr_test_1"
        assert payload["email"] == "user1@docqa.ai"
        assert payload["role"] == "Researcher"
        assert "exp" in payload

    def test_expired_or_invalid_token_fails(self):
        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.invalid_signature"
        with pytest.raises(jwt.PyJWTError):
            jwt.decode(fake_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

    def test_password_hashing_and_verification(self):
        password = "securePassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrongPassword", hashed) is False
        assert verify_password(password, None) is False

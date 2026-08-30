import hashlib
import hmac
import secrets

from app.core.config import settings

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """Хеширует пароль комнаты (pbkdf2 + случайная соль)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def sign_room_token(public_token: str) -> str:
    """Подпись токена комнаты для cookie авторизации."""
    return hmac.new(
        settings.secret_key.encode(),
        public_token.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_room_token(public_token: str, signature: str) -> bool:
    expected = sign_room_token(public_token)
    return hmac.compare_digest(expected, signature)

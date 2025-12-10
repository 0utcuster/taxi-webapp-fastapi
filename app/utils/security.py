import time
from jose import jwt, JWTError
from ..config import settings

def create_jwt(payload: dict) -> str:
    exp = int(time.time()) + settings.JWT_TTL_SEC
    return jwt.encode({**payload, "exp": exp}, settings.SECRET_KEY, algorithm=settings.JWT_ALG)

def decode_jwt(token: str):
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALG])
    except JWTError:
        return None
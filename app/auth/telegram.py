# app/auth/telegram.py
from __future__ import annotations
import hmac
import hashlib
import urllib.parse
from typing import Any, Dict, Optional

def _data_check_string(params: Dict[str, str]) -> str:
    # сортируем по ключу и склеиваем "key=value" через \n, исключая hash
    parts = []
    for k in sorted(params.keys()):
        if k == "hash":
            continue
        parts.append(f"{k}={params[k]}")
    return "\n".join(parts)

def verify_webapp_init_data(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    ВАЛИДАЦИЯ ДЛЯ TELEGRAM WEB APP:
    secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)  <-- ВАЖНО!
    hash = HMAC_SHA256(key=secret_key, msg=data_check_string)
    """
    if not init_data or not bot_token:
        return None

    # Разбираем query-string вида: query_id=...&user=%7B...%7D&auth_date=...&hash=...
    try:
        q = urllib.parse.parse_qs(init_data, keep_blank_values=True, strict_parsing=False)
        params: Dict[str, str] = {k: v[0] for k, v in q.items() if v}
    except Exception:
        return None

    recv_hash = params.get("hash")
    if not recv_hash:
        return None

    # ВНИМАНИЕ: для WEB APP secret отличается!
    # secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

    check_string = _data_check_string(params).encode("utf-8")
    calc_hash = hmac.new(secret_key, check_string, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, recv_hash):
        return None

    # Собираем ответ и декодируем user (json-строка)
    data: Dict[str, Any] = {}
    for k, v in params.items():
        if k == "user":
            try:
                import json
                data["user"] = json.loads(v)
            except Exception:
                data["user"] = None
        else:
            data[k] = v
    return data

# Совместимость со старым именем (если где-то звали)
def verify_telegram_auth(init_data: str, bot_token: str):
    return verify_webapp_init_data(init_data, bot_token)
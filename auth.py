import os
import secrets

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()


async def require_server_key(x_server_key: str | None = Header(default=None)):
    # Kljuc se nikad ne loguje i ne vraca u odgovoru.
    kljuc = os.getenv("SERVER_KEY", "")
    if not kljuc:
        raise HTTPException(status_code=503, detail="server key not configured")
    if x_server_key is None or not secrets.compare_digest(
        x_server_key.encode(), kljuc.encode()
    ):
        raise HTTPException(status_code=403, detail="forbidden")

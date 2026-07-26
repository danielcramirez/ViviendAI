from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


APP_DIR = Path(__file__).resolve().parent


def load_local_env() -> None:
    """Load simple KEY=VALUE entries without adding a runtime dependency."""
    env_path = APP_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def request_vivi_reply(
    payload: dict[str, Any],
    timeout: float = 20.0,
    max_retries: int = 1,
) -> dict[str, Any]:
    load_local_env()
    webhook_url = os.getenv("MAKE_STREAMLIT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("MAKE_STREAMLIT_WEBHOOK_URL no está configurada.")

    headers = {"Content-Type": "application/json"}
    make_api_key = os.getenv("MAKE_WEBHOOK_API_KEY", "").strip()
    if make_api_key:
        headers["x-make-apikey"] = make_api_key

    body = ""
    for attempt in range(max(0, max_retries) + 1):
        request = Request(
            webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
            break
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            retryable = error.code == 429 or 500 <= error.code <= 504
            if retryable and attempt < max_retries:
                header_delay = (error.headers or {}).get("Retry-After")
                match = re.search(r"retry in\s+([0-9.]+)s", detail, re.IGNORECASE)
                delay = (
                    float(header_delay)
                    if header_delay
                    else float(match.group(1)) if match else 7.0
                )
                time.sleep(min(max(delay, 1.0), 15.0))
                continue
            raise RuntimeError(
                f"Make respondió HTTP {error.code}: {detail[:250]}"
            ) from error
        except (URLError, TimeoutError) as error:
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(
                f"No fue posible contactar el webhook de Make: {error}"
            ) from error

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        result = {"ok": True, "reply": body.strip()}
    if not result.get("reply"):
        raise RuntimeError("La respuesta de Make no contiene el campo reply.")
    return result

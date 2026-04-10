from __future__ import annotations

import json
import os
import socket
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from a2wsgi import ASGIMiddleware
from waitress import serve

from api.api_server import app as fastapi_app


PROJECT_ROOT = Path(__file__).resolve().parent
SERVER_CONFIG_PATH = PROJECT_ROOT / "config" / "server.json"

DEFAULT_SERVER_CONFIG = {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": False,
    "workers": 4,
    "ssl_certfile": "",
    "ssl_keyfile": "",
}


def load_server_config() -> dict[str, Any]:
    if not SERVER_CONFIG_PATH.exists():
        SERVER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        SERVER_CONFIG_PATH.write_text(
            json.dumps(DEFAULT_SERVER_CONFIG, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return dict(DEFAULT_SERVER_CONFIG)

    try:
        payload = json.loads(SERVER_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_SERVER_CONFIG)

    if not isinstance(payload, dict):
        return dict(DEFAULT_SERVER_CONFIG)

    merged = dict(DEFAULT_SERVER_CONFIG)
    merged.update(payload)
    return merged


def _public_url(config: dict[str, Any]) -> str:
    host = str(config.get("host") or DEFAULT_SERVER_CONFIG["host"]).strip()
    port = int(config.get("port") or DEFAULT_SERVER_CONFIG["port"])
    scheme = "http"
    if host in {"0.0.0.0", "::"}:
        host = "localhost"
    return f"{scheme}://{host}:{port}"


def _ssl_ready(config: dict[str, Any]) -> bool:
    certfile = Path(str(config.get("ssl_certfile") or "")).expanduser()
    keyfile = Path(str(config.get("ssl_keyfile") or "")).expanduser()
    return bool(str(certfile)) and bool(str(keyfile)) and certfile.exists() and keyfile.exists()


def _wait_for_socket(host: str, port: int, timeout_seconds: float = 12.0) -> bool:
    deadline = time.time() + timeout_seconds
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    while time.time() < deadline:
        try:
            with socket.create_connection((probe_host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def _open_browser_when_ready(url: str, host: str, port: int) -> None:
    if _wait_for_socket(host, port):
        try:
            webbrowser.open(url)
        except Exception:
            pass


def main() -> None:
    config = load_server_config()
    host = "0.0.0.0"
    port = 5000
    threads = 4
    url = "http://localhost:5000"

    cert_path = str(
        Path(str(config.get("ssl_certfile") or PROJECT_ROOT / "config" / "cert.pem")).expanduser()
    )
    key_path = str(
        Path(str(config.get("ssl_keyfile") or PROJECT_ROOT / "config" / "key.pem")).expanduser()
    )

    print("AURA online. All systems operational.")
    print(f"Serving AURA at {url}")
    if os.path.exists(cert_path) and os.path.exists(key_path):
        print("SSL certificates detected, but this launcher is currently serving HTTP on localhost.")
        print("AURA online at http://localhost:5000")
    else:
        print("Running HTTP — no SSL certs found in config/")
        print("AURA online at http://localhost:5000")

    browser_thread = threading.Thread(
        target=_open_browser_when_ready,
        args=(url, host, port),
        daemon=True,
    )
    browser_thread.start()

    aura_app = ASGIMiddleware(fastapi_app)
    serve(aura_app, host="0.0.0.0", port=5000, threads=4)


if __name__ == "__main__":
    main()

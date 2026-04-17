from __future__ import annotations

import json
import os
import random
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DATA_PATH = Path(__file__).with_name("declaration_monopoly_cards.json")

with DATA_PATH.open("r", encoding="utf-8") as data_file:
    GAME_DATA = json.load(data_file)


class MonopolyAPIHandler(BaseHTTPRequestHandler):
    auth_enabled = os.getenv("SERVICE_AUTH_ENABLED", "false").lower() == "true"
    franceconnect_base_url = os.getenv("FRANCECONNECT_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    auth_timeout_seconds = float(os.getenv("AUTH_REQUEST_TIMEOUT_SECONDS", "2.5"))

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _require_auth(self) -> bool:
        if not self.auth_enabled:
            return True
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            self._send_json({"error": "Authentication required"}, status=HTTPStatus.UNAUTHORIZED)
            return False
        token = auth_header[7:].strip()
        if not token:
            self._send_json({"error": "Authentication required"}, status=HTTPStatus.UNAUTHORIZED)
            return False

        request = Request(
            f"{self.franceconnect_base_url}/auth/introspect",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.auth_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            self._send_json({"error": "Auth provider unavailable"}, status=HTTPStatus.SERVICE_UNAVAILABLE)
            return False

        if not payload.get("active"):
            self._send_json({"error": "Invalid token"}, status=HTTPStatus.UNAUTHORIZED)
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802 - standard BaseHTTPRequestHandler API
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/":
            self._send_json(
                {
                    "message": "Bienvenue sur l'API Déclaration Monopoly",
                    "endpoints": [
                        "/health",
                        "/cards",
                        "/cards/chance",
                        "/cards/communaute",
                        "/cards/chance/random",
                        "/cards/communaute/random",
                        "/taxes",
                    ],
                }
            )
            return

        if path == "/health":
            self._send_json({"status": "ok"})
            return

        if not self._require_auth():
            return

        if path == "/cards":
            self._send_json(
                {
                    "theme": GAME_DATA["theme"],
                    "currency": GAME_DATA["currency"],
                    "chance": GAME_DATA["chance"],
                    "communaute": GAME_DATA["communaute"],
                }
            )
            return

        if path in ("/cards/chance", "/cards/communaute"):
            deck = path.split("/")[-1]
            cards = GAME_DATA[deck]
            self._send_json({"deck": deck, "count": len(cards), "cards": cards})
            return

        if path in ("/cards/chance/random", "/cards/communaute/random"):
            deck = path.split("/")[-2]
            self._send_json({"deck": deck, "card": random.choice(GAME_DATA[deck])})
            return

        if path == "/taxes":
            self._send_json(GAME_DATA["impots"])
            return

        self._send_json({"error": "Route introuvable"}, status=HTTPStatus.NOT_FOUND)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = HTTPServer((host, port), MonopolyAPIHandler)
    print(f"API démarrée sur http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()

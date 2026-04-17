from __future__ import annotations

import json
import random
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

DATA_PATH = Path(__file__).with_name("declaration_monopoly_cards.json")

with DATA_PATH.open("r", encoding="utf-8") as data_file:
    GAME_DATA = json.load(data_file)


class MonopolyAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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

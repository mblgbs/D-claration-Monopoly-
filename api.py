from __future__ import annotations

import json
import os
import random
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

DATA_PATH = Path(__file__).with_name("declaration_monopoly_cards.json")

with DATA_PATH.open("r", encoding="utf-8") as data_file:
    GAME_DATA = json.load(data_file)


class MonopolyAPIHandler(BaseHTTPRequestHandler):
    auth_enabled = os.getenv("SERVICE_AUTH_ENABLED", "false").lower() == "true"
    franceconnect_base_url = os.getenv("FRANCECONNECT_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    auth_timeout_seconds = float(os.getenv("AUTH_REQUEST_TIMEOUT_SECONDS", "2.5"))
    bank_api_base_url = os.getenv("BANK_API_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
    joueur_to_compte: dict[str, int] = {}

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        return json.loads(raw.decode("utf-8"))

    def _bank_request(self, endpoint: str, method: str = "GET", payload: dict | None = None) -> dict:
        request = Request(
            f"{self.bank_api_base_url}{endpoint}",
            headers={"Content-Type": "application/json"},
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            method=method,
        )
        try:
            with urlopen(request, timeout=self.auth_timeout_seconds) as response:
                response_payload = response.read().decode("utf-8")
                return json.loads(response_payload) if response_payload else {}
        except HTTPError as err:
            details = err.read().decode("utf-8")
            try:
                parsed = json.loads(details)
                message = parsed.get("error", "Bank API error")
            except Exception:  # pragma: no cover - defensive
                message = "Bank API error"
            raise ValueError(message) from err
        except Exception as err:  # pragma: no cover - network issues
            raise ConnectionError("Bank API unavailable") from err

    def _ensure_joueur_compte(self, joueur: str) -> int:
        if joueur in self.joueur_to_compte:
            return self.joueur_to_compte[joueur]
        created = self._bank_request(
            "/comptes",
            method="POST",
            payload={"nom": joueur, "solde_initial": 1500},
        )
        compte_id = int(created["id"])
        self.joueur_to_compte[joueur] = compte_id
        return compte_id

    def _apply_bank_movement(self, joueur: str, montant: int) -> dict:
        compte_id = self._ensure_joueur_compte(joueur)
        if montant >= 0:
            return self._bank_request(
                f"/comptes/{compte_id}/retrait",
                method="POST",
                payload={"montant": montant},
            )
        return self._bank_request(
            f"/comptes/{compte_id}/depot",
            method="POST",
            payload={"montant": abs(montant)},
        )

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

        if path == "/bank/accounts":
            self._send_json({"mapping": self.joueur_to_compte})
            return

        self._send_json({"error": "Route introuvable"}, status=HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/declarations":
            self._send_json({"error": "Route introuvable"}, status=HTTPStatus.NOT_FOUND)
            return
        if not self._require_auth():
            return
        try:
            payload = self._read_json()
            joueur = str(payload.get("joueur", "")).strip()
            declaration_type = str(payload.get("type", "")).strip()
            evenement = str(payload.get("evenement", "")).strip()
            raw_montant = payload.get("montant", None)
            notes = str(payload.get("notes", "")).strip()

            if not joueur:
                self._send_json({"error": "Le joueur est requis"}, status=HTTPStatus.BAD_REQUEST)
                return
            if not declaration_type:
                self._send_json({"error": "Le type est requis"}, status=HTTPStatus.BAD_REQUEST)
                return
            if not evenement:
                self._send_json({"error": "L'évènement est requis"}, status=HTTPStatus.BAD_REQUEST)
                return
            if raw_montant is None or str(raw_montant).strip() == "":
                self._send_json({"error": "Le montant est requis"}, status=HTTPStatus.BAD_REQUEST)
                return
            if isinstance(raw_montant, bool):
                self._send_json({"error": "Le montant est invalide"}, status=HTTPStatus.BAD_REQUEST)
                return

            montant = int(raw_montant)

            bank_account = self._apply_bank_movement(joueur, montant)
            operation = "retrait" if montant >= 0 else "depot"
            self._send_json(
                {
                    "entry": {
                        "joueur": joueur,
                        "type": declaration_type,
                        "evenement": evenement,
                        "montant": montant,
                        "notes": notes,
                        "operation": operation,
                    },
                    "bankAccount": {
                        "id": bank_account["id"],
                        "nom": bank_account["nom"],
                        "solde": bank_account["solde"],
                    },
                },
                status=HTTPStatus.CREATED,
            )
        except ValueError as err:
            self._send_json({"error": str(err)}, status=HTTPStatus.BAD_REQUEST)
        except ConnectionError:
            self._send_json({"error": "Service bancaire indisponible"}, status=HTTPStatus.SERVICE_UNAVAILABLE)
        except Exception:
            self._send_json({"error": "Erreur interne"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


def run(host: str = "127.0.0.1", port: int = 8003) -> None:
    server = HTTPServer((host, port), MonopolyAPIHandler)
    print(f"API démarrée sur http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()

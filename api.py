from __future__ import annotations

import json
import os
import random
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

DATA_PATH = Path(__file__).with_name("declaration_monopoly_cards.json")
SERVICES_MONOPOLY_BASE_URL = os.getenv("SERVICES_MONOPOLY_BASE_URL", "http://127.0.0.1:8004").strip().rstrip("/")
INITIAL_BALANCE = 1500

with DATA_PATH.open("r", encoding="utf-8") as data_file:
    GAME_DATA = json.load(data_file)

DECLARATIONS: list[dict[str, object]] = []
PLAYER_BALANCES: dict[str, int] = {}


class MonopolyAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Corps JSON invalide") from exc
        if not isinstance(payload, dict):
            raise ValueError("Le corps JSON doit etre un objet")
        return payload

    def _create_payment_link(self, payload: dict[str, object]) -> str:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=f"{SERVICES_MONOPOLY_BASE_URL}/payments/link",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5.0) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = "Erreur service paiements"
            try:
                error_payload = json.loads(exc.read().decode("utf-8"))
                if isinstance(error_payload, dict):
                    raw_detail = error_payload.get("detail") or error_payload.get("error")
                    if isinstance(raw_detail, str) and raw_detail.strip():
                        detail = raw_detail.strip()
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            raise RuntimeError(detail) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Service paiements indisponible") from exc

        payment_url = data.get("url") if isinstance(data, dict) else None
        if not isinstance(payment_url, str) or not payment_url.strip():
            raise RuntimeError("Reponse service paiements invalide")
        return payment_url

    def do_GET(self) -> None:  # noqa: N802 - standard BaseHTTPRequestHandler API
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/":
            self._send_json(
                {
                    "message": "Bienvenue sur l'API Declaration Monopoly",
                    "endpoints": [
                        "/health",
                        "/cards",
                        "/cards/chance",
                        "/cards/communaute",
                        "/cards/chance/random",
                        "/cards/communaute/random",
                        "/taxes",
                        "POST /declarations",
                        "POST /payments/link",
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

    def do_POST(self) -> None:  # noqa: N802 - standard BaseHTTPRequestHandler API
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/declarations":
            try:
                payload = self._read_json_body()
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            joueur = str(payload.get("joueur", "")).strip()
            declaration_type = str(payload.get("type", "")).strip().lower()
            evenement = str(payload.get("evenement", "")).strip()
            notes = str(payload.get("notes", "")).strip()

            amount_raw = payload.get("montant")
            if isinstance(amount_raw, (int, float)):
                amount = int(amount_raw)
            else:
                self._send_json({"error": "Montant invalide"}, status=HTTPStatus.BAD_REQUEST)
                return

            if not joueur or not evenement or amount <= 0:
                self._send_json(
                    {"error": "Champs requis invalides (joueur, evenement, montant)."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            if declaration_type not in {"chance", "communaute", "impot"}:
                self._send_json(
                    {"error": "Type invalide. Utilisez chance, communaute ou impot."},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            operation = "debit" if declaration_type == "impot" else "credit"
            signed_amount = -amount if operation == "debit" else amount

            current_balance = PLAYER_BALANCES.get(joueur, INITIAL_BALANCE)
            updated_balance = current_balance + signed_amount
            PLAYER_BALANCES[joueur] = updated_balance

            entry = {
                "id": f"decl-{len(DECLARATIONS) + 1}",
                "joueur": joueur,
                "type": declaration_type,
                "evenement": evenement,
                "montant": amount,
                "notes": notes,
                "operation": operation,
            }
            DECLARATIONS.append(entry)

            self._send_json(
                {
                    "entry": entry,
                    "bankAccount": {
                        "joueur": joueur,
                        "solde": updated_balance,
                    },
                },
                status=HTTPStatus.CREATED,
            )
            return

        if path == "/payments/link":
            try:
                payload = self._read_json_body()
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            reference_id = str(payload.get("reference_id", "")).strip()
            context = str(payload.get("context", "tax")).strip() or "tax"
            metadata = payload.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            amount_hint_cents = payload.get("amount_hint_cents")
            if amount_hint_cents is not None:
                if not isinstance(amount_hint_cents, (int, float)) or amount_hint_cents <= 0:
                    self._send_json({"error": "amount_hint_cents invalide"}, status=HTTPStatus.BAD_REQUEST)
                    return
                amount_hint_cents = int(round(amount_hint_cents))

            if not reference_id:
                self._send_json({"error": "reference_id requis"}, status=HTTPStatus.BAD_REQUEST)
                return

            services_payload = {
                "app": "declaration",
                "context": context,
                "reference_id": reference_id,
                "metadata": metadata,
            }
            if amount_hint_cents is not None:
                services_payload["amount_hint_cents"] = amount_hint_cents

            try:
                payment_url = self._create_payment_link(services_payload)
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
                return

            self._send_json({"url": payment_url})
            return

        self._send_json({"error": "Route introuvable"}, status=HTTPStatus.NOT_FOUND)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = HTTPServer((host, port), MonopolyAPIHandler)
    print(f"API demarree sur http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run(port=int(os.getenv("PORT", "8000")))

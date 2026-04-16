import json
from dataclasses import dataclass, asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import urlparse


@dataclass
class Compte:
    id: int
    nom: str
    solde: int


class BanqueMonopoly:
    def __init__(self) -> None:
        self._comptes: dict[int, Compte] = {}
        self._next_id = 1
        self._lock = Lock()

    def creer_compte(self, nom: str, solde_initial: int) -> Compte:
        if not nom or not isinstance(nom, str):
            raise ValueError("Le nom est requis")
        if not isinstance(solde_initial, int) or solde_initial < 0:
            raise ValueError("Le solde_initial doit être un entier >= 0")

        with self._lock:
            compte = Compte(id=self._next_id, nom=nom, solde=solde_initial)
            self._comptes[self._next_id] = compte
            self._next_id += 1
            return compte

    def lister_comptes(self) -> list[Compte]:
        return list(self._comptes.values())

    def get_compte(self, compte_id: int) -> Compte:
        compte = self._comptes.get(compte_id)
        if compte is None:
            raise KeyError("Compte introuvable")
        return compte

    def depot(self, compte_id: int, montant: int) -> Compte:
        if not isinstance(montant, int) or montant <= 0:
            raise ValueError("Le montant doit être un entier > 0")
        with self._lock:
            compte = self.get_compte(compte_id)
            compte.solde += montant
            return compte

    def retrait(self, compte_id: int, montant: int) -> Compte:
        if not isinstance(montant, int) or montant <= 0:
            raise ValueError("Le montant doit être un entier > 0")
        with self._lock:
            compte = self.get_compte(compte_id)
            if compte.solde < montant:
                raise ValueError("Solde insuffisant")
            compte.solde -= montant
            return compte

    def transfert(self, source_id: int, destination_id: int, montant: int) -> dict[str, Compte]:
        if source_id == destination_id:
            raise ValueError("Les comptes source et destination doivent être différents")
        if not isinstance(montant, int) or montant <= 0:
            raise ValueError("Le montant doit être un entier > 0")

        with self._lock:
            source = self.get_compte(source_id)
            destination = self.get_compte(destination_id)
            if source.solde < montant:
                raise ValueError("Solde insuffisant")
            source.solde -= montant
            destination.solde += montant
            return {"source": source, "destination": destination}


bank = BanqueMonopoly()


class APIHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError as exc:
            raise ValueError("JSON invalide") from exc
        if not isinstance(data, dict):
            raise ValueError("Le corps JSON doit être un objet")
        return data

    def _send_json(self, status: int, payload: dict | list) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_error(self, status: int, message: str) -> None:
        self._send_json(status, {"erreur": message})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        if path == "/comptes":
            comptes = [asdict(c) for c in bank.lister_comptes()]
            self._send_json(200, comptes)
            return

        if path.startswith("/comptes/"):
            try:
                compte_id = int(path.split("/")[2])
                compte = asdict(bank.get_compte(compte_id))
                self._send_json(200, compte)
            except (ValueError, IndexError):
                self._handle_error(400, "ID de compte invalide")
            except KeyError as exc:
                self._handle_error(404, str(exc))
            return

        self._handle_error(404, "Route introuvable")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            data = self._read_json()

            if path == "/comptes":
                compte = bank.creer_compte(
                    nom=data.get("nom"),
                    solde_initial=data.get("solde_initial"),
                )
                self._send_json(201, asdict(compte))
                return

            if path.startswith("/comptes/") and path.endswith("/depot"):
                compte_id = int(path.split("/")[2])
                compte = bank.depot(compte_id, data.get("montant"))
                self._send_json(200, asdict(compte))
                return

            if path.startswith("/comptes/") and path.endswith("/retrait"):
                compte_id = int(path.split("/")[2])
                compte = bank.retrait(compte_id, data.get("montant"))
                self._send_json(200, asdict(compte))
                return

            if path == "/transferts":
                result = bank.transfert(
                    source_id=data.get("source_id"),
                    destination_id=data.get("destination_id"),
                    montant=data.get("montant"),
                )
                self._send_json(
                    200,
                    {
                        "source": asdict(result["source"]),
                        "destination": asdict(result["destination"]),
                    },
                )
                return

            self._handle_error(404, "Route introuvable")
        except ValueError as exc:
            self._handle_error(400, str(exc))
        except KeyError as exc:
            self._handle_error(404, str(exc))


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), APIHandler)
    print(f"API Monopoly disponible sur http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()

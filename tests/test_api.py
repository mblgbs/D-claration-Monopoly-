import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import api


class APITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), api.APIHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self) -> None:
        api.bank = api.BanqueMonopoly()

    def request_json(self, method: str, path: str, body: dict | None = None):
        payload = None
        headers = {}
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=payload,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_health(self):
        status, body = self.request_json("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")

    def test_creer_compte_et_lister(self):
        status, body = self.request_json("POST", "/comptes", {"nom": "Alice", "solde_initial": 1500})
        self.assertEqual(status, 201)
        self.assertEqual(body["nom"], "Alice")
        self.assertEqual(body["solde"], 1500)

        status, comptes = self.request_json("GET", "/comptes")
        self.assertEqual(status, 200)
        self.assertEqual(len(comptes), 1)

    def test_depot_retrait_transfert(self):
        _, a = self.request_json("POST", "/comptes", {"nom": "Alice", "solde_initial": 1500})
        _, b = self.request_json("POST", "/comptes", {"nom": "Bob", "solde_initial": 1500})

        status, body = self.request_json("POST", f"/comptes/{a['id']}/depot", {"montant": 200})
        self.assertEqual(status, 200)
        self.assertEqual(body["solde"], 1700)

        status, body = self.request_json("POST", f"/comptes/{a['id']}/retrait", {"montant": 100})
        self.assertEqual(status, 200)
        self.assertEqual(body["solde"], 1600)

        status, body = self.request_json(
            "POST",
            "/transferts",
            {"source_id": a["id"], "destination_id": b["id"], "montant": 300},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["source"]["solde"], 1300)
        self.assertEqual(body["destination"]["solde"], 1800)

    def test_erreur_solde_insuffisant(self):
        _, a = self.request_json("POST", "/comptes", {"nom": "Alice", "solde_initial": 50})
        status, body = self.request_json("POST", f"/comptes/{a['id']}/retrait", {"montant": 100})
        self.assertEqual(status, 400)
        self.assertIn("insuffisant", body["erreur"].lower())


if __name__ == "__main__":
    unittest.main()

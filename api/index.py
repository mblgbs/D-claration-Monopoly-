import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx

DATA_PATH = Path(__file__).parent.parent / "declaration_monopoly_cards.json"
SERVICES_MONOPOLY_BASE_URL = os.getenv("SERVICES_MONOPOLY_BASE_URL", "https://monopoly-services.vercel.app").rstrip("/")
INITIAL_BALANCE = 1500

with DATA_PATH.open("r", encoding="utf-8") as f:
    GAME_DATA = json.load(f)

DECLARATIONS: list[dict] = []
PLAYER_BALANCES: dict[str, int] = {}

app = FastAPI(title="Declaration Monopoly API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class DeclarationBody(BaseModel):
    joueur: str
    type: str
    evenement: str
    montant: int
    notes: Optional[str] = ""

class PaymentLinkBody(BaseModel):
    reference_id: str
    context: Optional[str] = "tax"
    metadata: Optional[dict] = {}
    amount_hint_cents: Optional[int] = None

@app.get("/")
def root():
    return {"message": "Bienvenue sur Declaration Monopoly API"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/cards")
def cards():
    return {"theme": GAME_DATA["theme"], "currency": GAME_DATA["currency"], "chance": GAME_DATA["chance"], "communaute": GAME_DATA["communaute"]}

@app.get("/cards/chance")
def cards_chance():
    return {"deck": "chance", "count": len(GAME_DATA["chance"]), "cards": GAME_DATA["chance"]}

@app.get("/cards/communaute")
def cards_communaute():
    return {"deck": "communaute", "count": len(GAME_DATA["communaute"]), "cards": GAME_DATA["communaute"]}

@app.get("/cards/chance/random")
def cards_chance_random():
    return {"deck": "chance", "card": random.choice(GAME_DATA["chance"])}

@app.get("/cards/communaute/random")
def cards_communaute_random():
    return {"deck": "communaute", "card": random.choice(GAME_DATA["communaute"])}

@app.get("/taxes")
def taxes():
    return GAME_DATA["impots"]

@app.post("/declarations", status_code=201)
def create_declaration(body: DeclarationBody):
    if body.type not in {"chance", "communaute", "impot"}:
        raise HTTPException(400, "Type invalide. Utilisez chance, communaute ou impot.")
    operation = "debit" if body.type == "impot" else "credit"
    signed = -body.montant if operation == "debit" else body.montant
    current = PLAYER_BALANCES.get(body.joueur, INITIAL_BALANCE)
    PLAYER_BALANCES[body.joueur] = current + signed
    entry = {"id": f"decl-{len(DECLARATIONS)+1}", "joueur": body.joueur, "type": body.type,
             "evenement": body.evenement, "montant": body.montant, "notes": body.notes, "operation": operation}
    DECLARATIONS.append(entry)
    return {"entry": entry, "bankAccount": {"joueur": body.joueur, "solde": PLAYER_BALANCES[body.joueur]}}

@app.post("/payments/link")
def payment_link(body: PaymentLinkBody):
    payload = {"app": "declaration", "context": body.context, "reference_id": body.reference_id, "metadata": body.metadata or {}}
    if body.amount_hint_cents:
        payload["amount_hint_cents"] = body.amount_hint_cents
    try:
        r = httpx.post(f"{SERVICES_MONOPOLY_BASE_URL}/payments/link", json=payload, timeout=5)
        r.raise_for_status()
        return {"url": r.json()["url"]}
    except Exception as e:
        raise HTTPException(502, f"Service paiements indisponible: {e}")

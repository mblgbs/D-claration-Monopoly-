# Déclaration Monopoly API

API REST simple pour exposer les cartes Monopoly du fichier `declaration_monopoly_cards.json`.

## Prérequis

- Python 3.10+

## Lancer l'API

```bash
python api.py
```

L'API sera disponible sur :
- `http://127.0.0.1:8000`

## Endpoints

- `GET /health` : état du service.
- `GET /` : message d'accueil + liste des endpoints.
- `GET /cards` : toutes les cartes (Chance + Communauté).
- `GET /cards/chance` : cartes Chance.
- `GET /cards/communaute` : cartes Communauté.
- `GET /cards/chance/random` : carte Chance aléatoire.
- `GET /cards/communaute/random` : carte Communauté aléatoire.
- `GET /taxes` : règles et montants des impôts.

## Exemples

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/cards/chance/random
```

## Authentification FranceConnect (MVP SSO)

Cette API peut protéger toutes les routes métier via un token Bearer issu de `FranceConnect-Monopoly`.

Variables d'environnement:

- `SERVICE_AUTH_ENABLED=true`
- `FRANCECONNECT_BASE_URL=http://127.0.0.1:8000`
- `AUTH_REQUEST_TIMEOUT_SECONDS=2.5`

Comportement:

- `/health` et `/` restent publics
- les routes `/cards*` et `/taxes` exigent `Authorization: Bearer <token>`
- token invalide/manquant -> `401`
- fournisseur d'auth indisponible -> `503`

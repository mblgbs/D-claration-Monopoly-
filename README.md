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

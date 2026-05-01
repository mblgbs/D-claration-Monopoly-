# Déclaration Monopoly API

API REST simple pour exposer les cartes Monopoly du fichier `declaration_monopoly_cards.json`.

**Écosystème :** `GET http://127.0.0.1:8004/ecosystem` sur [services-Monopoly-](../services-Monopoly-/README.md#decouverte-des-services-ecosystem) liste les URLs (cette API : `8003` en runbook local).

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

## Ecriture et paiements

- Nouveau endpoint: `POST /declarations` (enregistrement declaration + mise a jour solde en memoire).
- Nouveau endpoint: `POST /payments/link` (proxy vers `services-Monopoly-` pour lien Stripe).
- Variable d'environnement: `SERVICES_MONOPOLY_BASE_URL` (defaut `http://127.0.0.1:8004`).

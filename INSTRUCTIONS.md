# Swing Trading Screener — Instructions de lancement

## Prérequis
- Python 3.10+
- Node.js 18+

---

## 1. Backend (FastAPI)

```bash
cd backend

# Créer un environnement virtuel
python -m venv venv

# Activer (Windows)
venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer le serveur
uvicorn main:app --reload --port 8000
```

L'API sera disponible sur http://localhost:8000
Documentation interactive : http://localhost:8000/docs

---

## 2. Frontend (Next.js)

Dans un second terminal :

```bash
cd frontend

# Installer les dépendances
npm install

# Lancer en mode développement
npm run dev
```

Le dashboard sera disponible sur http://localhost:3000

---

## Structure du projet

```
ANALYSE SWING/
├── backend/
│   ├── main.py           # API FastAPI + algorithme d'analyse
│   └── requirements.txt  # Dépendances Python
└── frontend/
    ├── app/
    │   ├── page.tsx               # Page principale (Server Component)
    │   ├── types.ts               # Types TypeScript
    │   └── components/
    │       ├── Dashboard.tsx      # Dashboard interactif
    │       ├── ScreenerTable.tsx  # Tableau principal
    │       ├── ScoreBadge.tsx     # Badge score coloré
    │       └── StatusBadge.tsx    # Badge statut
    ├── .env.local                 # URL de l'API
    └── package.json
```

---

## Endpoints API

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | /api/screener | Analyse tous les tickers |
| GET | /api/screener/{ticker} | Analyse un ticker spécifique |
| GET | /api/tickers | Liste des tickers surveillés |

---

## Tickers surveillés (40 valeurs)

AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, JPM, V, UNH,
MA, HD, PG, JNJ, AVGO, LLY, COST, MRK, ABBV, CRM,
AMD, NFLX, ACN, TMO, DHR, ADBE, TXN, NEE, QCOM, INTU,
BRK-B, WMT, CVX, XOM, BAC, NOW, AMGN, PLD, ISRG, SPGI

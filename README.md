# 🤖 Chatbot Portfolio Backend

Backend d'API REST développé avec **FastAPI** et propulsé par le modèle `gpt-oss-120b` via l'**API Albert** (Etalab). Ce service alimente le chatbot interactif d'un portfolio de développeur, permettant aux recruteurs et visiteurs de poser des questions sur le parcours, les compétences et les prétentions salariales de manière concise et guidée.

---

## 🛠️ Stack Technique

* **Framework :** FastAPI (Python)
* **Serveur ASGI :** Uvicorn
* **IA / LLM :** API Albert (`gpt-oss-120b`) via le client officiel `openai`
* **Sécurité & Rate Limiting :** `slowapi` (limite de requêtes par IP)
* **Conteneurisation :** Docker & Docker Compose
* **Reverse Proxy / SSL :** Nginx Proxy Manager (HTTPS)

---

## 📁 Structure du Projet

```text
chatbot-portfolio/
├── app/
│   ├── app.py              # Logique principale de l'API FastAPI et prompt système
│   └── requirements.txt    # Dépendances Python
├── .dockerignore           # Fichiers ignorés par Docker
├── .env                    # Variables d'environnement locales (non versionné)
├── .gitignore              # Fichiers ignorés par Git
├── compose.yaml            # Configuration Docker Compose
└── Dockerfile              # Instructions de construction de l'image
```

---

## ⚙️ Configuration et Installation

### 1. Cloner le projet
```bash
git clone https://github.com/LGBhackinho/chatbot-portfolio-API.git
cd chatbot-portfolio-API
```

### 2. Configurer les secrets
Le projet utilise une clé d'API Albert sécurisée. 
* En production (Docker), la clé est injectée via les secrets Docker (`/run/secrets/albert_api_key`) ou un fichier `.env`.
* Crée un fichier `.env` à la racine si tu testes en local hors Docker :
  ```env
  ALBERT_API_KEY=ta_cle_api_albert_ici
  ```

---

## 🚀 Lancement avec Docker

Pour lancer le service proprement en arrière-plan avec Docker Compose :

```bash
# Construire l'image sans cache et lancer le conteneur
docker compose build --no-cache
docker compose up -d
```

Le service écoutera par défaut sur le port configuré (ex: `8001` en externe).

---

## 🔌 Utilisation de l'API

### Endpoint principal : `POST /chat`

* **URL :** `https://ton-domaine.com/chat` (via ton reverse proxy Nginx Proxy Manager)
* **Headers :** `Content-Type: application/json`
* **Body (JSON) :**
  ```json
  {
    "message": "Quelles sont vos prétentions salariales ?"
  }
  ```
* **Réponse (JSON) :**
  ```json
  {
    "response": "Les prétentions salariales de TOTO se situent entre 30 000 € et 34 000 € brut annuel..."
  }
  ```

---

## 🔒 Sécurité

* **Rate Limiting :** Limité à 10 requêtes par minute et par adresse IP pour éviter les abus (`slowapi`).
* **CORS :** Configuré pour autoriser les requêtes sécurisées depuis le frontend du portfolio.
* **Isolation :** Les clés sensibles sont exclues du versioning Git grâce au `.gitignore`.
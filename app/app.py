import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 1. Chargement de la clé API depuis le secret monté
SECRET_PATH = "/run/secrets/albert_api_key"
if os.path.exists(SECRET_PATH):
    with open(SECRET_PATH, "r") as f:
        api_key = f.read().strip()
else:
    api_key = os.getenv("ALBERT_API_KEY", "")

if not api_key:
    raise RuntimeError("Clé API Albert introuvable !")

client = OpenAI(
    base_url="https://albert.api.etalab.gouv.fr/v1",
    api_key=api_key,
)

# Modèle fixe défini proprement ici
SELECTED_MODEL = "gpt-oss-120b"

# 2. Configuration du Rate Limiter (ex: max 10 requêtes / minute par IP)
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 3. CORS
# Liste des origines autorisées (Dev + Prod GitHub Pages)
# Liste des origines autorisées (SANS slash à la fin)
origins = [
    "https://lgbhackinho.github.io",  # Ton portfolio GitHub Pages
    "http://192.168.1.22:8080",
    "http://localhost:5500",           # VS Code Live Server (port par défaut)
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Autorise toutes les méthodes (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Autorise tous les en-têtes
)

# Route de preflight OPTIONS
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    return {}

# 4. Définition du Prompt Système
SYSTEM_PROMPT = """
Tu es l'assistant du portfolio de Ruddy (Développeur Web Full Stack & Concepteur d'Application à Poitiers).
Tu réponds aux recruteurs et aux visiteurs de manière courtoise, directe et concise.

RÈGLES DE RÉPONSE :
1. Fais des réponses courtes (2 à 3 lignes maximum).
2. Saute toujours des lignes pour aérer ton texte.
3. Si la question utilise "vous" ou "vos" (ex: "vos prétentions", "votre salaire"), réponds directement concernant Ruddy.
4. Si la question est totalement hors-sujet (météo, cuisine), indique gentiment que tu ne réponds qu'aux questions sur le parcours de Ruddy.

EXEMPLE SALAIRE ET PRÉTENTIONS :
Question: Quelles sont vos prétentions salariales ? (ou "son salaire", "prétentions")
Réponse:
Les prétentions salariales de Ruddy se situent entre 30 000 € et 34 000 € brut annuel, selon le poste, les responsabilités et le mode de travail (télétravail/présentiel). Mais si vous lui proposez plus, il dira pas non ;). la touche d'humour est importante car j'aime l humour masi tu le dit pas masi laisse le smiley.

INFORMATIONS À CONNAÎTRE SUR RUDDY :
- Prétentions salariales : Entre 30 000 € et 34 000 € brut par an.
- Disponibilité : À partir de février 2027 (Poitiers / Télétravail, Permis B).
- Poste recherché : Développeur Web / Mobile Full Stack, Concepteur d'Application.
- Diplômes : Développeur Web & Web Mobile Full Stack (RNCP 37674 - IFPA Poitiers), BTS M.A.I.
- Compétences : PHP, JavaScript, React/Next.js, Python, SQL/MySQL, Linux, Bash, Docker, Android (Java).
- Expériences : Concepteur d'application à Réseau Canopé (2025-2026), Stage dev mobile CHBL Laborit (2024), Technicien Courant Faible / Sécurité chez Bouygues (2009-2024), Automaticien chez Bouygues (2001-2009).
- Contact : ruddy.86.m@gmail.com
"""

class ChatQuery(BaseModel):
    message: str = Field(..., max_length=200)  

@app.post("/chat")
@limiter.limit("10/minute")
async def chat_endpoint(request: Request, query: ChatQuery):
    try:
        response = client.chat.completions.create(
            model=SELECTED_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query.message}
            ],
            max_tokens=200,
            temperature=0.4
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        print(f"--- ERREUR CHAT EXACTE : {e} ---", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
import os
import httpx
import re
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
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

# Configuration Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

client = OpenAI(
    base_url="https://albert.api.etalab.gouv.fr/v1",
    api_key=api_key,
)

SELECTED_MODEL = "gpt-oss-120b"

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [
    "https://lgbhackinho.github.io",
    "http://192.168.1.22:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    return {}

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
Les prétentions salariales de Ruddy se situent entre 30 000 € et 34 000 € brut annuel, selon le poste, les responsabilités et le mode de travail (télétravail/présentiel). Mais si vous lui proposez plus, il dira pas non ;). La touche d'humour est importante car j'aime l humour masi tu le dit pas masi laisse le smiley.

INFORMATIONS À CONNAÎTRE SUR RUDDY :
- Prétentions salariales : Entre 30 000 € et 34 000 € brut par an.
- Disponibilité : À partir de février 2027 (Poitiers / Télétravail, Permis B).
- Poste recherché : Développeur Web / Mobile Full Stack, Concepteur d'Application.
- Diplômes : Développeur Web & Web Mobile Full Stack (RNCP 37674 - IFPA Poitiers), BTS M.A.I.
- Compétences : PHP, JavaScript, React/Next.js, Python, SQL/MySQL, Linux, Bash, Docker, Android (Java).
- Expériences : Concepteur d'application à Réseau Canopé (2025-2026), Stage develeppement application Android au CHBL Laborit (2024), Technicien Courant Faible / Sécurité chez Bouygues (2009-2024), Automaticien chez Bouygues (2001-2009).
- Contact : ruddy.86.m@gmail.com
"""

class ChatQuery(BaseModel):
    message: str = Field(..., max_length=200)  

async def send_telegram_notification(user_message: str, bot_reply: str):
    """Envoie une alerte Telegram propre"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré (Token ou Chat ID manquant).", flush=True)
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = (
        f"🚨 *Nouveau message sur ton portfolio !*\n\n"
        f"👤 *Visiteur :* {user_message}\n"
        f"🤖 *IA :* {bot_reply}"
    )
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "markdown"
    }
    
    async with httpx.AsyncClient() as client_http:
        try:
            response = await client_http.post(url, json=payload, timeout=5.0)
            if response.status_code != 200:
                print(f"Erreur Telegram API : {response.text}", flush=True)
        except Exception as e:
            print(f"Erreur connexion Telegram : {e}", flush=True)

def clean_ai_response(text: str) -> str:
    """Supprime les blocs de réflexion interne <think>...</think> si le modèle les génère"""
    # Enlève tout ce qui est entre <think> et </think>
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Supprime aussi les phrases de réflexion isolées
    cleaned = re.sub(r'Réflexion en cours\.\.\.', '', cleaned)
    return cleaned.strip()

@app.post("/chat")
@limiter.limit("10/minute")
async def chat_endpoint(request: Request, query: ChatQuery, background_tasks: BackgroundTasks):
    try:
        response = client.chat.completions.create(
            model=SELECTED_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query.message}
            ],
            max_tokens=600,  # <-- Augmenté de 200 à 600 pour éviter les réponses coupées
            temperature=0.4
        )
        
        raw_reply = response.choices[0].message.content
        bot_reply = clean_ai_response(raw_reply)

        # Notification Telegram avec la réponse nettoyée
        background_tasks.add_task(send_telegram_notification, query.message, bot_reply)

        return {"response": bot_reply}
    except Exception as e:
        print(f"--- ERREUR CHAT EXACTE : {e} ---", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
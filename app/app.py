import os
import httpx
import re
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import des clients selon les besoins
from openai import OpenAI
import google.generativeai as genai

# 1. Choix du fournisseur d'IA (albert ou gemini)
AI_PROVIDER = os.getenv("AI_PROVIDER", "albert").lower()

client_openai = None
SELECTED_MODEL = ""

if AI_PROVIDER == "gemini":
    # --- CONFIGURATION GEMINI ---
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_api_key:
        raise RuntimeError("Clé API Gemini introuvable !")
    
    genai.configure(api_key=gemini_api_key)
    SELECTED_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

else:
    # --- CONFIGURATION ALBERT (OpenAI-compatible) ---
    SECRET_PATH = "/run/secrets/albert_api_key"
    if os.path.exists(SECRET_PATH):
        with open(SECRET_PATH, "r") as f:
            api_key = f.read().strip()
    else:
        api_key = os.getenv("ALBERT_API_KEY", "")

    if not api_key:
        raise RuntimeError("Clé API Albert introuvable !")

    client_openai = OpenAI(
        base_url="https://albert.api.etalab.gouv.fr/v1",
        api_key=api_key,
    )
    SELECTED_MODEL = os.getenv("ALBERT_MODEL", "gpt-oss-120b")

# Configuration Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

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
Tu es l'assistant recrutement du portfolio de Ruddy (Développeur Web / Mobile Full Stack à Poitiers).
Ton rôle est de répondre aux visiteurs et recruteurs de façon claire, directe, courtoise et convaincante, en mettant en valeur le profil de Ruddy.

RÈGLES DE RÉPONSE :
1. Réponses courtes (2 à 4 lignes max), aérées avec des sauts de ligne.
2. Si la question utilise "vous" ou "vos", réponds directement au sujet de Ruddy.
3. Si la question est hors-sujet, indique poliment que tu réponds uniquement au sujet du parcours, des projets et de la candidature de Ruddy.
4. Ne dis rien de négatif sur Ruddy. Pour ses défauts, présente un point d'amélioration constructif et non bloquant.
5. Mention Telegram : ne répète PAS systématiquement à chaque message que Ruddy reçoit des notifications Telegram. Mentionne-le uniquement lors du premier échange si pertinent, ou lorsqu'un visiteur souhaite contacter Ruddy / laisser ses coordonnées.
6. Évite les phrases creuses du type "je vous invite à découvrir sur le portfolio" quand on te pose une question précise : donne des faits concrets.

PROJETS PERSONNELS :
- JobPilot : Application web développée avec Symfony (PHP 8.x), Twig, CSS/JS natifs et stockage JSON local pour centraliser la recherche d'emploi. Elle gère le suivi des candidatures classiques et spontanées, l'analyse de CV, le matching CV ↔ offre, la génération de lettres de motivation, la préparation d'entretien, un tableau de bord avec graphiques CSS/HTML, un cache anti-quota et une recherche combinant Adzuna, Jooble et l'API officielle recherche-entreprises (codes NAF).
- Briefing Matinal IA : Application full stack (backend Node.js, frontend Vite) générant un briefing audio quotidien (météo, actualités, point dev, résumé des e-mails via IMAP et offres d'emploi développeur) via Gemini ou Mistral avec recherche web, planifié avec n8n et lu à voix haute (navigateur, Piper en local, ElevenLabs ou Google TTS).
- Chatbot Portfolio API : Backend REST en Python (FastAPI, Uvicorn) conteneurisé avec Docker et exposé en HTTPS via Nginx Proxy Manager, alimentant l'assistant du portfolio (API Albert / Gemini) avec rate limiting (slowapi) et notifications Telegram.
- Plateforme de suivi nutritionnel : Site web conçu pour aider un coach nutritionnel à suivre ses clients, partager des recettes et faciliter la compréhension de la nutrition et des calculs caloriques.
- Projet le plus intéressant / représentatif à mettre en avant : JobPilot (sous Symfony), car c'est un outil complet que ruddy utilise au quotidien qui combine architecture métier structurée, intégration multi-IA avec cache intelligent, croisement d'API externes et interface sur mesure sans dépendance lourde.

CONSIGNES SPÉCIFIQUES :
- "Pourquoi choisir Ruddy plutôt qu'un autre ?" : mets en avant sa double culture terrain/technique (ancienne expérience d'automaticien et technicien courant faible chez Bouygues + développement web/mobile full stack), sa capacité d'adaptation rapide et ses projets concrets.
- Prétentions salariales : entre 30 000 € et 34 000 € brut / an selon poste et modalités, avec une touche d'humour légère à la fin (ex: "Mais s'il y a plus sur la table, il saura s'adapter ;)").
- Philosophie / Entretien :
  * Motivation : concevoir des outils utiles et résoudre des problèmes concrets de bout en bout.
  * Adaptation : rigueur de diagnostic acquise sur le terrain, sens du relationnel et autonomie face à des technologies nouvelles.
  * Point d'amélioration : tendance à vouloir livrer une qualité irréprochable très vite, qu'il cadre avec des priorités claires.
- Contact direct / Entretien : donne l'email ruddy.86.m@gmail.com, invite le visiteur à laisser message ou coordonnées, et précise que Ruddy est notifié sur Telegram et répondra rapidement.

INFORMATIONS CLÉS SUR RUDDY :
- Prétentions : 30 000 € à 34 000 € brut / an.
- Disponibilité : à partir de février 2027 (Poitiers / Télétravail, Permis B).
- Cibles : Développeur Web / Mobile Full Stack, Concepteur d'Application.
- Diplômes : Développeur Web & Web Mobile Full Stack (RNCP 37674 - IFPA Poitiers), BTS M.A.I.
- Stack : PHP, JavaScript, React/Next.js, Python, SQL/MySQL, Linux, Bash, Docker, Android (Java) — apprend vite les nouveaux langages.
- Expériences : Concepteur d'application à Réseau Canopé (2025-2026), Stage dev Android au CHBL Laborit (2024), Technicien Courant Faible / Sécurité chez Bouygues (2009-2024), Automaticien chez Bouygues (2001-2009).
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
        f"🤖 *IA ({AI_PROVIDER}) :* {bot_reply}"
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
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'Réflexion en cours\.\.\.', '', cleaned)
    return cleaned.strip()

@app.post("/chat")
@limiter.limit("10/minute")
async def chat_endpoint(request: Request, query: ChatQuery, background_tasks: BackgroundTasks):
    try:
        raw_reply = ""

        if AI_PROVIDER == "gemini":
            # Appel de l'API Gemini officiel avec system_instruction
            model = genai.GenerativeModel(
                model_name=SELECTED_MODEL,
                system_instruction=SYSTEM_PROMPT
            )
            response = model.generate_content(
                query.message,
                generation_config={
                    "max_output_tokens": 600,
                    "temperature": 0.4
                }
            )
            raw_reply = response.text
        else:
            # Appel de l'API Albert (OpenAI compatible d'origine)
            response = client_openai.chat.completions.create(
                model=SELECTED_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": query.message}
                ],
                max_tokens=600,
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
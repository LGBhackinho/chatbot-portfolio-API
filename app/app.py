import os
import re
from typing import List, Optional
import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from openai import OpenAI
import google.generativeai as genai

# 1. Choix du fournisseur d'IA (albert ou gemini)
AI_PROVIDER = os.getenv("AI_PROVIDER", "albert").lower()

client_openai = None
SELECTED_MODEL = ""

if AI_PROVIDER == "gemini":
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_api_key:
        raise RuntimeError("Clé API Gemini introuvable !")
    genai.configure(api_key=gemini_api_key)
    SELECTED_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
else:
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
Tu es l'agent de talents et assistant recrutement dédié de Ruddy (Développeur Web / Mobile Full Stack à Poitiers).
Tu échanges avec des recruteurs et des visiteurs sur son portfolio. Ton objectif est de qualifier leur besoin et de donner envie de rencontrer Ruddy.

POSTURE & STYLE D'UN VRAI AGENT DE RECRUTEMENT :
- Parle de Ruddy avec naturel, recul et conviction, comme un vrai chargé de recrutement qui connaît bien son candidat. Évite les superlatifs creux ("passionné", "hors pair", "débordant").
- Privilégie des phrases fluides et naturelles plutôt que des listes à puces, sauf si le visiteur demande explicitement d'énumérer ses projets ou compétences.
- Relie systématiquement son parcours (15 ans d'expérience terrain comme automaticien et technicien chez Bouygues + reconversion réussie en développement Full Stack & intégration IA) aux enjeux concrets du recruteur.
- Si une technologie demandée n'est pas dans sa stack, sois transparent et fais le pont avec une compétence proche qu'il maîtrise déjà.
- Termine régulièrement (environ 1 fois sur 2, pas à chaque message) par une courte question de qualification (poste visé, stack technique, télétravail ou sur place, échéance) ou propose de transmettre un message directement à Ruddy.

RÈGLES DE FORMAT & SÉCURITÉ :
1. Réponses courtes, directes et synthétiques, aérées avec des sauts de ligne entre les idées (3 à 5 lignes maximum, environ 60 à 80 mots). Ne fais jamais de longs pavés : résume l'essentiel et propose d'approfondir si le visiteur le souhaite.
2. Si la question utilise "vous" ou "vos" (ex: "vos prétentions", "votre disponibilité"), réponds directement au sujet de Ruddy.
3. Si la question est hors-sujet (météo, cuisine, etc.), recadre poliment en précisant que tu es là pour échanger sur le profil et les projets de Ruddy.
4. Ne dis rien de négatif sur Ruddy. Sur ses points d'amélioration, présente un axe constructif et non bloquant.
5. Mention Telegram : ne répète JAMAIS à chaque message que Ruddy reçoit des notifications Telegram. Mentionne-le uniquement si le visiteur cherche à le joindre, demande sa disponibilité ou laisse ses coordonnées.
6. Ne renvoie jamais le visiteur "découvrir sur le portfolio" quand il pose une question précise : donne des faits concrets.

CONSIGNES MÉTIER :
- "Pourquoi choisir Ruddy ?" : mets en avant sa double culture terrain/technique (rigueur de diagnostic acquise chez Bouygues face aux incidents critiques + capacité à concevoir des outils web/IA complets de bout en bout) et son sens du relationnel client/équipe.
- Prétentions salariales : entre 30 000 € et 34 000 € brut annuel selon le poste et les modalités, avec une touche d'humour légère à la fin (ex: "Mais si votre budget prévoit un peu plus, il saura s'adapter ;)").
- Point d'amélioration : exigeant sur la qualité de ses livrables, il a tendance à vouloir tout peaufiner très vite, un réflexe qu'il canalise en priorisant l'essentiel.
- Passage en contact direct / Entretien : donne son email direct (ruddy.86.m@gmail.com) et propose au visiteur de laisser son nom, son entreprise ou son email/téléphone ici même, en précisant que Ruddy est alerté en temps réel sur Telegram et répond rapidement.

PROJETS PERSONNELS :
- JobPilot : Application web développée avec Symfony (PHP 8.x), Twig, CSS/JS natifs et stockage JSON local pour centraliser sa recherche d'emploi. Gère le suivi des candidatures classiques et spontanées, l'analyse de CV, le matching CV ↔ offre, les lettres de motivation, la préparation d'entretien, un tableau de bord analytique, un cache anti-quota et une recherche combinant Adzuna, Jooble et l'API officielle recherche-entreprises (codes NAF).
- Briefing Matinal IA : Application full stack (backend Node.js, frontend Vite) générant chaque matin un briefing audio personnalisé (météo, actualités, point dev, résumé des e-mails via IMAP et offres d'emploi développeur) via Gemini ou Mistral avec recherche web, automatisé avec n8n et lu à voix haute (navigateur, Piper en local, ElevenLabs ou Google TTS).
- Chatbot Portfolio API : Backend REST en Python (FastAPI, Uvicorn) conteneurisé avec Docker et exposé en HTTPS via Nginx Proxy Manager, alimentant cet assistant (API Albert / Gemini) avec rate limiting (slowapi), gestion sécurisée des secrets et notifications Telegram.
- Plateforme de suivi nutritionnel : Site web conçu pour aider un coach nutritionnel à suivre ses clients, partager des recettes et faciliter la compréhension de la nutrition et des calculs caloriques.
- Projet le plus intéressant / représentatif à mettre en avant : JobPilot (sous Symfony), car c'est une application métier complète utilisée au quotidien qui combine architecture structurée, intégration multi-IA avec cache intelligent et croisement d'API externes.

INFORMATIONS CLÉS SUR RUDDY :
- Disponibilité : à partir de février 2027 (Poitiers / Télétravail, Permis B).
- Postes recherchés : Développeur Web / Mobile Full Stack, Concepteur d'Application.
- Diplômes : Développeur Web & Web Mobile Full Stack (RNCP 37674 - IFPA Poitiers), BTS M.A.I.
- Stack technique : PHP, Symfony, JavaScript, React / Next.js, Node.js, Python (FastAPI), SQL / MySQL, Linux, Bash, Docker, Android (Java), intégration d'API IA (Gemini, Mistral, Albert).
- Expériences : Concepteur d'application à Réseau Canopé (2025-2026), Stage développement application Android au CHBL Laborit (2024), Technicien Courant Faible / Sécurité chez Bouygues (2009-2024), Automaticien chez Bouygues (2001-2009).
- Contact : ruddy.86.m@gmail.com
"""

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=1000)

class ChatQuery(BaseModel):
    message: str = Field(..., max_length=300)
    history: Optional[List[ChatMessage]] = Field(default_factory=list)

def detect_lead(text: str) -> bool:
    """Détecte si le visiteur laisse un email ou un numéro de téléphone"""
    has_email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text) is not None
    has_phone = re.search(r'(?:0|\+33)[1-9](?:[\s.-]?\d{2}){4}', text) is not None
    return has_email or has_phone

async def send_telegram_notification(user_message: str, bot_reply: str):
    """Envoie une alerte Telegram (prioritaire si un contact est détecté)"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré (Token ou Chat ID manquant).", flush=True)
        return

    is_lead = detect_lead(user_message)
    header = "🔥 *LEAD RECRUTEUR DÉTECTÉ sur ton portfolio !*" if is_lead else "🚨 *Nouveau message sur ton portfolio !*"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = (
        f"{header}\n\n"
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
    """Supprime les blocs de réflexion interne si le modèle les génère"""
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'Réflexion en cours\.\.\.', '', cleaned)
    return cleaned.strip()

@app.post("/chat")
@limiter.limit("10/minute")
async def chat_endpoint(request: Request, query: ChatQuery, background_tasks: BackgroundTasks):
    try:
        raw_reply = ""
        # On garde uniquement les 6 derniers messages pour maîtriser les tokens
        recent_history = (query.history or [])[-6:]

        if AI_PROVIDER == "gemini":
            model = genai.GenerativeModel(
                model_name=SELECTED_MODEL,
                system_instruction=SYSTEM_PROMPT
            )
            gemini_contents = []
            for msg in recent_history:
                role = "model" if msg.role == "assistant" else "user"
                gemini_contents.append({"role": role, "parts": [msg.content]})
            gemini_contents.append({"role": "user", "parts": [query.message]})

            response = model.generate_content(
                gemini_contents,
                generation_config={
                    "max_output_tokens": 300,
                    "temperature": 0.45
                }
            )
            raw_reply = response.text
        else:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for msg in recent_history:
                messages.append({"role": msg.role, "content": msg.content})
            messages.append({"role": "user", "content": query.message})

            response = client_openai.chat.completions.create(
                model=SELECTED_MODEL,
                messages=messages,
                max_tokens=600,
                temperature=0.45
            )
            raw_reply = response.choices[0].message.content

        bot_reply = clean_ai_response(raw_reply)

        background_tasks.add_task(send_telegram_notification, query.message, bot_reply)

        return {"response": bot_reply}

    except Exception as e:
        print(f"--- ERREUR CHAT EXACTE : {e} ---", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
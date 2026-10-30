FROM python:3.11-slim

# Sécurité : création d'un utilisateur non-root
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Installation directe et forcée de toutes les dépendances sans passer par requirements.txt
RUN pip install --no-cache-dir fastapi==0.110.0 uvicorn==0.28.0 openai==1.14.1 httpx==0.27.2 slowapi==0.1.9 pydantic==2.6.4 python-dotenv==1.0.1 google-generativeai

COPY . .

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000","--reload"]
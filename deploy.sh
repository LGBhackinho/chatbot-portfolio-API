#!/bin/bash
echo "🚀 Mise à jour du chatbot backend..."
docker compose down
docker compose build --no-cache
docker compose up -d
echo "✅ C'est en ligne !"
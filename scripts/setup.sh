#!/usr/bin/env bash
# NexaDesk — first-time setup helper
# Run: bash scripts/setup.sh

set -e

echo "======================================"
echo "  NexaDesk Setup"
echo "======================================"

# 1. Check .env
if [ ! -f ".env" ]; then
  echo "[1/5] Creating .env from .env.example..."
  cp .env.example .env
  echo "      -> Edit .env and add your API keys, then re-run this script."
  exit 0
else
  echo "[1/5] .env found."
fi

# 2. Check required keys
required_vars=(LLM_API_KEY SUPABASE_URL SUPABASE_SERVICE_KEY EMBED_API_KEY)
missing=()
for var in "${required_vars[@]}"; do
  val=$(grep "^${var}=" .env | cut -d'=' -f2)
  [ -z "$val" ] && missing+=("$var")
done

if [ ${#missing[@]} -gt 0 ]; then
  echo "ERROR: Missing required .env values:"
  for var in "${missing[@]}"; do
    echo "  - $var"
  done
  echo "Fill these in .env and re-run."
  exit 1
fi
echo "      API keys present."

# 3. Build and start containers
echo "[2/5] Starting Docker containers..."
docker compose up -d --build
echo "      Waiting for services to be ready..."
sleep 8

# 4. Run Supabase schema (reminder)
echo "[3/5] Supabase schema:"
echo "      Run alembic/schema.sql in your Supabase SQL Editor if not done."
echo "      (Supabase → SQL Editor → New Query → paste → Run)"

# 5. Seed demo data
echo "[4/5] Seeding demo data..."
docker compose exec app python scripts/seed_demo.py

# 6. Dashboard
echo "[5/5] Dashboard setup..."
if [ -d "dashboard/node_modules" ]; then
  echo "      node_modules already installed."
else
  echo "      Installing dashboard dependencies..."
  cd dashboard && npm install && cd ..
fi

if [ ! -f "dashboard/.env" ]; then
  cp dashboard/.env.example dashboard/.env
  echo "      -> Edit dashboard/.env with your VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY"
fi

echo ""
echo "======================================"
echo "  Setup Complete!"
echo "======================================"
echo ""
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Dashboard: cd dashboard && npm run dev (http://localhost:3000)"
echo ""
echo "  To run the dashboard:"
echo "    cd dashboard && npm run dev"
echo ""

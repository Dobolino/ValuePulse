#!/usr/bin/env bash
# Startet ValuePulse per Doppelklick oder im Terminal.
set -u
cd "$(dirname "$0")"

export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "Python fehlt."
  echo "Bitte installiere Python 3.11 oder neuer:"
  echo "https://www.python.org/downloads/"
  echo "Danach diese Datei erneut starten."
  echo ""
  read -r -p "Enter drücken zum Schließen …" _
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Einrichtung beim ersten Start …"
  python3 -m venv .venv || {
    echo "Die Einrichtung ist fehlgeschlagen."
    read -r -p "Enter drücken zum Schließen …" _
    exit 1
  }
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"

if ! python -c "import streamlit, pandas, requests, dotenv" >/dev/null 2>&1; then
  echo "Bausteine werden installiert. Das kann ein bis zwei Minuten dauern …"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt || {
    echo "Die Installation ist fehlgeschlagen."
    read -r -p "Enter drücken zum Schließen …" _
    exit 1
  }
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp ".env.example" ".env"
  echo "Hinweis: .env wurde angelegt. Ohne API-Schlüssel startet der Demo-Modus."
fi

echo "ValuePulse öffnet sich im Browser. Dieses Fenster offen lassen."
exec streamlit run valuepulse/app.py --server.port 8501

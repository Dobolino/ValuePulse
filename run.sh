#!/usr/bin/env bash
# Startet ValuePulse im Hintergrund und öffnet das dunkle Dashboard.
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

port_open() {
  python -c "import socket; socket.create_connection(('127.0.0.1',8501),1)" >/dev/null 2>&1
}

open_browser() {
  url="http://localhost:8501"
  if command -v open >/dev/null 2>&1; then
    open "$url"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  else
    echo "Bitte öffne $url im Browser."
  fi
}

if port_open; then
  echo "ValuePulse läuft bereits. Das Dashboard öffnet sich im Darkmode."
  open_browser
  exit 0
fi

nohup python -m streamlit run valuepulse/app.py \
  --server.port 8501 \
  --server.headless true \
  --theme.base dark \
  --browser.gatherUsageStats false \
  >> valuepulse.log 2>&1 &
echo $! > .valuepulse.pid
disown >/dev/null 2>&1 || true

for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if port_open; then
    open_browser
    echo "ValuePulse wurde gestartet. Das Dashboard öffnet sich im Darkmode."
    exit 0
  fi
  sleep 1
done

echo "Der Start dauert länger als gedacht. Details stehen in valuepulse.log."
exit 1

#!/usr/bin/env bash
# Holt neue Dateien und aktualisiert die Python-Bausteine.
set -u
cd "$(dirname "$0")"

echo "ValuePulse wird aktualisiert …"
echo "Geholt wird die Hauptversion main."

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Dieser Ordner ist kein Git-Projekt. Die Version von main kann so nicht geholt werden."
  exit 1
fi

if ! git fetch origin main; then
  echo "Die Hauptversion main konnte nicht vom Server geholt werden."
  exit 1
fi

if git show-ref --verify --quiet refs/heads/main; then
  git checkout main || {
    echo "Wechsel auf main ist fehlgeschlagen. Bitte ValuePulse schließen und es erneut versuchen."
    exit 1
  }
else
  git checkout -b main --track origin/main || {
    echo "Die Hauptversion main ließ sich nicht öffnen."
    exit 1
  }
fi

if ! git pull --ff-only origin main; then
  echo "main konnte nicht übernommen werden."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python fehlt. Die Aktualisierung ist fehlgeschlagen."
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv || {
    echo "Die Aktualisierung ist fehlgeschlagen."
    exit 1
  }
fi

# shellcheck disable=SC1091
source ".venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || {
  echo "Die Aktualisierung ist fehlgeschlagen."
  exit 1
}

echo "ValuePulse wurde erfolgreich aktualisiert!"

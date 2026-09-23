#!/usr/bin/env bash
# Holt neue Dateien und aktualisiert die Python-Bausteine.
set -u
cd "$(dirname "$0")"

echo "ValuePulse wird aktualisiert …"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git fetch origin >/dev/null 2>&1; then
    if git status -sb | grep -q "behind"; then
      git pull --ff-only || echo "Hinweis: Neue Dateien konnten nicht automatisch übernommen werden."
    else
      echo "Keine neuen Dateien auf dem Server."
    fi
  else
    echo "Hinweis: Der Abgleich mit dem Server war gerade nicht möglich."
  fi
else
  echo "Kein Versionsstand zum Abgleichen. Es werden die Python-Bausteine aktualisiert."
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

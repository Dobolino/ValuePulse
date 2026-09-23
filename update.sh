#!/usr/bin/env bash
# Holt die Hauptversion main. Ein Ordner ohne Git lädt das ZIP von main.
# Schlüssel (.env) und die Datenbank bleiben erhalten.
set -u

if [ "${VP_FROM_TEMP:-}" != "1" ]; then
  stage="$(mktemp -d)"
  cp "$0" "$stage/update.sh"
  VP_FROM_TEMP=1 exec bash "$stage/update.sh" "$PWD"
fi

cd "$1"

echo "ValuePulse wird aktualisiert …"
echo "Geholt wird die Hauptversion main."

fetch_zip() {
  local dest="$1"
  local source="${VALUEPULSE_MAIN_ZIP:-https://github.com/Dobolino/ValuePulse/archive/refs/heads/main.zip}"
  if [ -f "$source" ]; then
    cp "$source" "$dest"
    return
  fi
  curl -fsSL -o "$dest" "$source"
}

apply_zip() {
  local zip="$1"
  local dest="$2"
  local unpack root
  unpack="$(mktemp -d)"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$zip" -d "$unpack"
  elif command -v python3 >/dev/null 2>&1; then
    python3 -m zipfile -e "$zip" "$unpack"
  else
    tar -xf "$zip" -C "$unpack"
  fi
  root="$(find "$unpack" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [ -z "$root" ] || [ ! -f "$root/run.bat" ]; then
    echo "Die heruntergeladene ZIP enthält ValuePulse nicht."
    return 1
  fi
  tar -C "$root" \
    --exclude=".git" \
    --exclude=".venv" \
    --exclude="__pycache__" \
    --exclude=".pytest_cache" \
    --exclude=".env" \
    --exclude="valuepulse.sqlite3" \
    --exclude="*.sqlite3" \
    --exclude="*.sqlite3.bak" \
    --exclude=".valuepulse.pid" \
    -cf - . | tar -C "$dest" -xf -
}

if [ -e .git ] && command -v git >/dev/null 2>&1; then
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
else
  echo "Kein Git-Ordner. Die Hauptversion main wird als ZIP geladen."
  echo "Eigene Schlüssel und die Datenbank bleiben erhalten."
  zip="$(mktemp)"
  if ! fetch_zip "$zip"; then
    echo "Die Hauptversion main konnte nicht heruntergeladen werden."
    echo "Bitte diese Datei im Browser laden, entpacken und run.sh starten:"
    echo "https://github.com/Dobolino/ValuePulse/archive/refs/heads/main.zip"
    exit 1
  fi
  if ! apply_zip "$zip" "$PWD"; then
    exit 1
  fi
fi

if [ "${VALUEPULSE_UPDATE_FILES_ONLY:-}" = "1" ]; then
  echo "ValuePulse wurde erfolgreich aktualisiert!"
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python fehlt. Die Dateien von main sind geholt. Danach ./run.sh starten."
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

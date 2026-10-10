#!/usr/bin/env bash
# Doppelklick-Aktualisierung für den Mac. Ruft dasselbe Skript wie das Terminal auf.
cd "$(dirname "$0")"
./update.sh
status=$?
echo ""
read -r -p "Enter drücken zum Schließen …" _
exit "$status"

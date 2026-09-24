# ValuePulse

ValuePulse vergleicht ein einfaches Tor-Modell mit Buchmacher-Quoten und markiert einen mathematischen Vorteil ab **3 % Edge**.

Das Dashboard läuft lokal im Browser. Fehlen API-Schlüssel oder ist ein Abruf-Limit erreicht, schaltet das Programm auf gespeicherte Quoten oder auf Beispiel-Daten um. Es bricht dabei nicht ab.

## Zum ersten Mal öffnen

### Windows

1. Öffne diesen Ordner.
2. Doppelklicke auf **run.bat**.
3. Beim ersten Start richtet das Programm alles selbst ein. Das kann ein bis zwei Minuten dauern.
4. Das Dashboard öffnet sich im Browser, im dunklen Design: <http://localhost:8501>

ValuePulse läuft danach im Hintergrund. Zum Beenden das minimierte Fenster „ValuePulse“ schließen.

### Mac

1. Öffne diesen Ordner.
2. Doppelklicke auf **run.command**.
3. Falls macOS die Datei blockiert: Rechtsklick → **Öffnen** → noch einmal **Öffnen**.
4. Das Dashboard öffnet sich im Browser: <http://localhost:8501>

Im Terminal geht auch: `./run.sh`

### Linux

Im Projektordner: `./run.sh`

Dieselbe Anleitung steht im Dashboard im Reiter **Hilfe**.

## Echte Spiele statt Demo

Ohne Schlüssel startet der Demo-Modus. Schlüssel trägst du im Reiter **Einstellungen** ein und speicherst sie mit **Schlüssel lokal speichern**. Alternativ geht eine Datei `.env` (Vorlage: `.env.example`):

```
FOOTBALL_DATA_API_KEY=dein_token
ODDS_API_KEY=dein_key
```

- Token: <https://www.football-data.org/client/register>
- Schlüssel: <https://the-odds-api.com/>

Danach neu starten und im Dashboard auf **Daten aktualisieren** klicken.

Jede abgerufene Quote landet in `valuepulse.sqlite3`. Quoten, die älter als 24 Stunden sind, senken die Datenqualität. Die Bewertung läuft trotzdem, ein Value-Signal bleibt dann gelb.

## Ampel

- Grün: Vorteil über 3 % und gute Daten. Beispiel: *Tipp: Heimsieg | Edge: 5,2 %*
- Gelb: Vorteil rechnerisch da, Daten dünn oder Quote veraltet.
- Rot/Grau: kein Vorteil gegenüber dem Buchmacher.

Links liegt die Navigation. Im **Kalender** wählst du den Zeitraum. Gerechnet wird erst nach **Spiele für gewählten Zeitraum berechnen**. Unter **Positionen** siehst du, ob gespeicherte Tipps gewonnen haben.

Neue Dateien holst du mit **update.bat** oder `./update.sh`. Dabei wird die Hauptversion **main** geholt. Ein ZIP-Ordner ohne Git lädt dieselben Dateien direkt; `.env` und `valuepulse.sqlite3` bleiben erhalten.

ValuePulse ist eine Rechenhilfe, keine Wettberatung.

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/pytest
```

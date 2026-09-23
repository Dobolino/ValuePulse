"""Hilfe-Text für das Dashboard und die README.

Der Text erklärt den ersten Start in einfachem Deutsch.
"""

HELP_MARKDOWN = """
# So öffnest du ValuePulse zum ersten Mal

ValuePulse vergleicht ein einfaches Tor-Modell mit den Quoten der Buchmacher.
Liegt der Vorteil (**Edge**) über 3 %, zeigt das Dashboard ein Signal.
Ohne Programmieren, ohne Einrichtung im Terminal.

## Windows

1. Öffne den Ordner von ValuePulse.
2. Doppelklicke auf **run.bat**.
3. Beim ersten Start richtet das Programm Python und die nötigen Bausteine selbst ein.
   Das kann ein bis zwei Minuten dauern. Ein schwarzes Fenster bleibt dabei offen.
4. Danach öffnet sich das Dashboard im Browser.
   Falls nicht, öffne selbst diese Adresse: [http://localhost:8501](http://localhost:8501)

Das schwarze Fenster nicht schließen, solange du ValuePulse benutzt.
Zum Beenden das Fenster schließen oder darin `Strg + C` drücken.

## Mac

1. Öffne den Ordner von ValuePulse.
2. Doppelklicke auf **run.command**.
3. Falls macOS warnt („nicht geöffnet, weil der Entwickler nicht verifiziert ist“):
   Rechtsklick auf die Datei, dann **Öffnen**, dann noch einmal **Öffnen**.
4. Beim ersten Start richtet das Programm alles selbst ein.
5. Danach öffnet sich das Dashboard im Browser
   ([http://localhost:8501](http://localhost:8501)).

Alternativ im Terminal, im Ordner von ValuePulse: `./run.sh`

## Linux

Im Ordner von ValuePulse im Terminal: `./run.sh`

## API-Schlüssel (nur für echte Spiele)

Ohne Schlüssel läuft ValuePulse sofort im **Demo-Modus** mit Beispielspielen.
Das ist gewollt und kein Fehler.

Für echte Spiele und Quoten brauchst du zwei kostenlose Schlüssel:

1. Konto bei [football-data.org](https://www.football-data.org/client/register) anlegen
   und den Token kopieren.
2. Konto bei [the-odds-api.com](https://the-odds-api.com/) anlegen
   und den API-Key kopieren.
3. Im Ordner von ValuePulse die Datei `.env.example` kopieren und die Kopie
   **`.env`** nennen.
4. Die beiden Schlüssel hinter die Namen schreiben, ohne Anführungszeichen:

```
FOOTBALL_DATA_API_KEY=dein_token
ODDS_API_KEY=dein_key
```

5. ValuePulse neu starten und im Dashboard auf **Daten aktualisieren** klicken.

## Die Ampel

- **Grün – Value-Tipp.** Das Modell sieht einen Vorteil über 3 % und die Daten
  sind frisch. Beispiel: *Tipp: Heimsieg | Edge: 5,2 %*.
- **Gelb – eingeschränkt.** Ein Vorteil ist rechnerisch da, die Datenbasis ist
  aber dünn oder die Quote ist älter als 24 Stunden.
  Hinweis: *Tipp theoretisch möglich, aber Datenqualität verringert.*
- **Grau/Rot – kein Value.** Der Markt ist fair oder teurer als das Modell.
  Hinweis: *Kein Vorteil gegenüber dem Buchmacher.*

Unter jedem Spiel steht in Klartext, warum das Signal so ausfällt.
Beispiel: *Modell sieht Heimsieg bei 60 %, Quote entspricht 52 % → 8,0 % Edge.*

## Wenn etwas hakt

- **Schlüssel fehlen oder das Abruf-Limit ist voll (HTTP 429):**
  ValuePulse stürzt nicht ab. Es nutzt gespeicherte Quoten aus
  `valuepulse.sqlite3` und zieht Punkte bei der Datenqualität ab.
  Liegt nichts Speicherbares vor, erscheint der Demo-Modus.
- **Quote älter als 24 Stunden:** Das Spiel wird trotzdem bewertet.
  Die Datenqualität sinkt, ein Value-Signal bleibt deshalb gelb.
- **Fenster schließt sich sofort:** Python ist nicht installiert oder nicht im PATH.
  Installiere Python 3.11 oder neuer von [python.org](https://www.python.org/downloads/)
  und starte die Datei erneut. Unter Windows beim Installieren
  „Add python.exe to PATH“ ankreuzen.

## Wichtig

ValuePulse ist eine Rechenhilfe, keine Wettberatung.
Quoten ändern sich. Ein angezeigter Edge ist keine Gewinnzusage.
Setze nur Geld, dessen Verlust du verkraften kannst.
"""

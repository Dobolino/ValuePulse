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
   Das kann ein bis zwei Minuten dauern.
   Python 3.11 oder neuer ist richtig. Python 3.13 ist passend.
4. Danach öffnet sich das Dashboard im Browser, dunkel hinterlegt.
   Falls nicht, öffne selbst diese Adresse: [http://localhost:8501](http://localhost:8501)

ValuePulse läuft im Hintergrund. Ein minimiertes Fenster bleibt in der Taskleiste.
Zum Beenden dieses Fenster schließen.

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

## Die Reiter oben

- **Dashboard:** die Ampel und die Begründung zu jedem Spiel.
- **Datums-Filter:** Start- und Enddatum wählen. Es wird noch nichts gerechnet.
  Erst der Button **Spiele suchen & berechnen** startet die Analyse.
- **Einstellungen:** Football-Data- und Odds-API-Schlüssel eintragen und mit
  **Schlüssel lokal speichern** sichern. Dort steht auch, ob der Demo-Modus aktiv ist
  und ob die Schlüssel gültig sind.
- **Pro-Version:** Poisson-Matrix, Buchmacher-Marge, Shin- und Power-Methode, Edge und Kelly-Anteil.
- **Hilfe:** diese Anleitung.

## API-Schlüssel (nur für echte Spiele)

Ohne Schlüssel läuft ValuePulse sofort im **Demo-Modus** mit Beispielspielen.
Das ist gewollt und kein Fehler.

So trägst du die Schlüssel ein:

1. Konto bei [football-data.org](https://www.football-data.org/client/register) anlegen
   und den Token kopieren.
2. Konto bei [the-odds-api.com](https://the-odds-api.com/) anlegen
   und den API-Key kopieren.
3. Im Reiter **Einstellungen** beide Felder ausfüllen.
4. Auf **Schlüssel lokal speichern** klicken.
5. Im Dashboard auf **Daten aktualisieren** klicken.

Die Schlüssel liegen danach in der Datei `.env` auf deinem Rechner.

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

## Aktualisieren

Neue Programmdateien holst du mit einem Doppelklick auf **update.bat** (Windows)
oder im Terminal mit `./update.sh` (Mac und Linux).
Dabei wird immer die Hauptversion **main** geholt.
Ein als ZIP gespeicherter Ordner ohne Git funktioniert trotzdem:
die Dateien werden direkt geladen. Die Schlüssel in `.env` und die Datei
`valuepulse.sqlite3` bleiben erhalten.
Wenn es geklappt hat, steht dort: *ValuePulse wurde erfolgreich aktualisiert!*

## Wenn etwas hakt

- **Schlüssel fehlen oder das Abruf-Limit ist voll (HTTP 429):**
  ValuePulse stürzt nicht ab. Es nutzt gespeicherte Quoten aus
  `valuepulse.sqlite3` und zieht Punkte bei der Datenqualität ab.
  Liegt nichts Speicherbares vor, erscheint der Demo-Modus.
- **Quote älter als 24 Stunden:** Das Spiel wird trotzdem bewertet.
  Die Datenqualität sinkt, ein Value-Signal bleibt deshalb gelb.
- **„Python wurde nicht gefunden“ und der Microsoft Store:** Windows hat kein echtes
  Python, nur eine Verknüpfung. Installiere Python 3.11 oder neuer von
  [python.org](https://www.python.org/downloads/) und kreuze dabei
  „Add python.exe to PATH“ an. Stelle danach unter
  Einstellungen → Apps → Erweiterte App-Einstellungen → App-Ausführungsaliase
  die Einträge `python.exe` und `python3.exe` auf Aus. Dann `run.bat` erneut starten.

## Wichtig

ValuePulse ist eine Rechenhilfe, keine Wettberatung.
Quoten ändern sich. Ein angezeigter Edge ist keine Gewinnzusage.
Setze nur Geld, dessen Verlust du verkraften kannst.
"""

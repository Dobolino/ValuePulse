# ValuePulse

ValuePulse vergleicht ein einfaches Tor-Modell mit Buchmacher-Quoten und markiert einen mathematischen Vorteil bei **mehr als 3 % EV** innerhalb definierter Schutzgrenzen.

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

- Grün: Vorteil über 3 % und gute Daten. Beispiel: *Tipp: Heimsieg | EV: 5,2 %*
- Gelb: Vorteil rechnerisch da, Daten dünn oder Quote veraltet.
- Rot/Grau: kein freigegebenes Value-Signal; Quoten, EV oder Daten erfüllen die Regeln nicht.

Links liegt die Navigation. Im **Kalender** wählst du den Zeitraum. Gerechnet wird erst nach **Spiele für gewählten Zeitraum berechnen**. Unter **Positionen** siehst du, ob gespeicherte Tipps gewonnen haben.

Neue Dateien holst du mit **update.bat** oder `./update.sh`. Dabei wird die Hauptversion **main** geholt. Ein ZIP-Ordner ohne Git lädt dieselben Dateien direkt; `.env` und `valuepulse.sqlite3` bleiben erhalten.

ValuePulse ist eine Rechenhilfe, keine Wettberatung.

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/pytest
```

## Validierte Tipps und neue Auswertungen

**EV ist jetzt der erwartete Nettoertrag je eingesetzter Einheit:**
`EV = Modellwahrscheinlichkeit × angebotene Quote − 1`.
55 % bei Quote 2,00 ergeben 10 % EV. Ein Abstand in Prozentpunkten zur
Buchmacherwahrscheinlichkeit ist eine andere Größe.

Die Scheinerstellung bewertet jede Auswahl **zuerst mit den tatsächlichen Preisen
eines Buchmachers**. Es gibt keinen Rückfall auf gemischte Bestquoten. Es gelten:

- EV größer als 3 % und höchstens 15 %; größere Rohwerte bleiben sichtbar,
  werden aber als auffällig gesperrt und nicht künstlich gekürzt.
- Datenqualität mindestens 60; vorhandene Tabellen mit mindestens fünf Spielen
  je verwendetem Team, höchstens 24 Stunden alt und mit passender Saison.
- Einzelquote höchstens 8, Gesamtquote höchstens 100, keine gemeinsamen Teams.
- Kein bereits begonnenes Spiel, keine Demo- oder unbestätigte Quote.
- Beim Button **Quoten prüfen & Tippschein generieren** erfolgt ein neuer Abruf.
  Nur echte Providerpreise mit bekanntem Zeitstempel und einem Alter von höchstens
  15 Minuten gelten als bestätigt. Der Zeitstempel des Abrufs ersetzt keinen
  fehlenden Quotenzeitstempel.

Die Kombichance setzt unabhängige Ergebnisse voraus. „Wenig Risiko“ bezeichnet
nur die Filter je Auswahl, keine Verlustgarantie für die Kombination.
Viertel-Kelly ist beim Schein auf 1 / 1,5 / 2 % nach Risikostufe begrenzt; die
Pro-Einzelansicht begrenzt zusätzlich auf 1 % und setzt bei unspielbaren Daten 0 %.

### Prognosen & Backtest

Live-Abrufe speichern unveränderliche Prognosesnapshots einschließlich
Modellversion, Eingangs-Tabellen, Saison, Quoten und Zeitstempeln. Im neuen
Navigationspunkt **Prognosen & Backtest** lassen sich bestätigte Endergebnisse
manuell erfassen und korrigieren; jede Änderung wird protokolliert.

Die Auswertung wählt je Spiel, Anbieter und Modellversion die erste oder letzte
vor Anpfiff aufgezeichnete Prognose. Sie zeigt Stichprobengröße, simulierten ROI
bei konstant einer Einheit pro damals qualifiziertem Tipp, Brier Score, Log Loss,
eine Markt-Baseline und Kalibrierungsgruppen. Prognosen und Auswertung sind als CSV
exportierbar. Demo- und nach Anpfiff erstellte Vorhersagen zählen nicht.

**Das ist ein Replay der ab jetzt gesammelten Prognosen.** Es gibt keine
rückwirkend verfügbaren historischen Prognosen, keinen historischen Datensatz
im Repository und keine nachgewiesene Profitabilität. Ergebnisse im Backtest
ändern Positionen nicht automatisch. Totals/Spreads und weitere Sportarten sind
weiterhin nicht an eine eigene Datenpipeline angeschlossen; die Power-Funktion
kann nun auch zwei Outcomes verarbeiten.

### Getrennte Positionsbücher und offene Einsätze

In der Sidebar stehen **Paper-Trading**, **Echtpositionen (manuell)** und
**Altbestand (Herkunft unbekannt)** zur Verfügung. Neue Einträge starten standardmäßig
im Paper-Buch. Die Bilanzen vermischen diese Kategorien nicht. Demo-Beispiele
können in keines der beiden neuen Bücher übernommen werden.

Einzelne validierte Tipps und ganze Scheine lassen sich protokollieren. Das
Positionsbuch zeigt den gesamten offenen Einsatz, dessen Verhältnis zur
angegebenen Bankroll und Überschneidungen je Team. Bei über 10 % offenem Einsatz
erscheint ein Hinweis; dies ist keine automatische Sperre und ersetzt keine
Portfolio-Optimierung. Bei Kombinationen zählt der volle Einsatz je beteiligtem
Team, diese Team-Zeilen sind daher nicht additiv. CSV-Export ist enthalten.
Die App gibt zu keinem Zeitpunkt Wetten bei einem Anbieter ab.

### Quotenverlauf

Unter **Strategie → Pro → Quotenverlauf** werden gespeicherte echte Quoten je
Spiel und Anbieter dargestellt und können exportiert werden. Der Verlauf wächst
mit den manuellen Abrufen; es gibt keinen Hintergrundsammler und keine
rekonstruierten historischen Preise.

### Abrufe und dauerhafte Daten

Ein Datensatz bleibt bis zu einer ausdrücklichen Aktualisierung in der Sitzung.
Kalender- und Navigationsklicks erzeugen keine weiteren API-Abrufe. Neue Abrufe
passieren beim Start einer neuen Sitzung, beim Aktualisieren, beim bestätigten
Zeitraumwechsel, bei einer Quotenprüfung oder nach dem Speichern neuer Schlüssel.
Alte Anzeigen können sichtbar bleiben, aber spielbare Tipps werden erneut geprüft.

Tabellen haben weiterhin eine Refresh-TTL von 24 Stunden. Fehlende saisonale
Metadaten führen bis zum nächsten erfolgreichen Abruf zu gesperrten Tipps.
Bei Quotenfehlern werden vorhandene Daten der fehlenden Ligen ergänzt, wenn sie
im Zeitraum liegen. Ohne Odds-Schlüssel können vorhandene Snapshots angezeigt
werden; sie zählen nicht als frische Quotenbestätigung.

Das SQLite-Schema wird additiv migriert. Vorhandene Positionen erhalten die
Kategorie **Altbestand**, da ihre frühere Herkunft nicht verlässlich bestimmbar
ist. Fehler, unbekannte Schema-Versionen und beschädigte Dateien führen **nicht**
mehr zum automatischen Ersetzen der Datenbank. Vor einem Update eine Kopie von
`valuepulse.sqlite3` aufbewahren; bei einer beschädigten Datei ist eine manuelle
Wiederherstellung erforderlich.

Die aktuelle Architektur und die Grenzen stehen in [ARCHITECTURE.md](ARCHITECTURE.md).
Entwicklertests einschließlich Streamlit-Interaktionen:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q --cov=valuepulse --cov-branch
```

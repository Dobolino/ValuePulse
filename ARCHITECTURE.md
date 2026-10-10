# ValuePulse: implementierte Architektur

ValuePulse ist eine lokale Streamlit-Anwendung. Sie arbeitet mit einer lokalen
SQLite-Datei und besitzt keine redundante Serverarchitektur oder garantierte
Hochverfügbarkeit. Es werden keine Wetten automatisch abgegeben.

## Module und Datenfluss

1. `providers.py`: Football-Data liefert kommende Fußballspiele und saisonale
   Gesamttabellen. The Odds API liefert 1X2-Quoten aus EU, ersatzweise UK.
   Nicht endliche Preise und unlesbare Datensätze werden verworfen. Unbekannte
   Quotenzeitstempel bleiben unbekannt.
2. `pipeline.py`: Abfrage, ligaweiser Cache-Fallback, Tabellen-Refresh und
   Vor-Anpfiff-Filter. Bestehende Datensätze können zur Information angezeigt
   werden; spielbare Tipps benötigen aktuelle Tabellen einschließlich passender
   Saison und bestätigte Providerpreise. Ohne brauchbare Daten wird eine klar
   markierte Demo angezeigt. Vorhersagen werden nach dem Datenabruf zeitgestempelt.
3. `model.py`: Poisson-Baseline mit Tor-/Gegentorschnitten, konstantem Shrinkage
   und Heim-/Auswärtsfaktor. Mindestens fünf gespielte Partien je verwendeter
   Mannschaft und vier verwendbare Ligateams sind nötig. Es werden keine
   aktuellen Aufstellungen oder Verletzungen modelliert. `edge` enthält EV;
   `probability_gap` enthält den separaten Abstand in Wahrscheinlichkeitspunkten.
4. `pro.py`: Shin und Power aus dem vollständigen Markt genau eines Anbieters;
   Power akzeptiert zwei oder mehr benannte Outcomes. Dies allein bedeutet keine
   Provider-Unterstützung für Totals oder Spreads. Kelly wird aus Modell und
   tatsächlich angebotener Quote gerechnet.
5. `slip.py`: Je Anbieter alle drei Ausgänge mit dessen konkreter Quote prüfen,
   Kandidaten nach Risikoprofil sortieren, gemeinsame Teams und Gesamtquoten über
   100 vermeiden. Die Auswahl ist eine Heuristik je Anbieter, kein erschöpfender
   Kombinationsoptimierer. Ohne vollständige Buchmacherzeilen kein Tipp.
6. `history.py`: Unveränderliche Prognosen, versionierte Eingangs-Snapshots,
   explizit erfasste Ergebnisse mit Änderungsprotokoll, zeitlich gefiltertes
   Replay und Abfrage echter Quotenverläufe.
7. `positions.py`: Paper-, Echt- und Altbestand getrennt, manuelles Settlement
   mit Änderungsprotokoll, G&V, ROI und offene Exposition. Einheiten sind vom
   Nutzer definierte Beträge. Der Bankroll-Wert ist eine manuelle Bezugsgröße,
   kein automatisches Bankkonto oder Ein-/Auszahlungsbuch.
8. `app.py` und `analytics_ui.py`: Darstellung aus dem letzten Sitzungsdatensatz,
   ausdrücklich ausgelöste Abrufe, Quotenprüfung vor neuer Scheinerstellung,
   Bücherwahl, Eingabe finaler Ergebnisse, Charts und CSV-Downloads.

## Persistenz und Migration

`db.py` verwaltet Schema-Version 2. Version 1 wird additiv um Saisonfelder
für Tabellen erweitert. Das Positionsschema wird beim Öffnen des Positionsbuchs
additiv um Modus, Buchmacher, Herkunft, Modellversion, Eventschlüssel und
Scheinbestandteile erweitert. Bestehende Einträge bleiben erhalten und sind als
`legacy` markiert. Die Tabellen `predictions`, `results`, `result_changes` und
`position_changes` ergänzen die bisherigen Tabellen.

Verbindungen haben begrenzte Lock-Retries. I/O-Fehler, volle Datenträger,
unbekannte Schemata und Beschädigungen werden gemeldet; es gibt keinen
automatischen Neuaufbau, kein Umbenennen und kein Überschreiben vorhandener
Backups. SQLite bleibt eine gemeinsame Datei für alle Datenarten. Wer eine
Cache-Bereinigung benötigt, darf deshalb nicht die komplette Datei löschen.
Quotensnapshots werden nach 90 Tagen entfernt, Prognosen und Positionen nicht.

Eventschlüssel bestehen aus Wettbewerb, normalisierten Teams und UTC-Anpfiff.
Eine Verlegung erzeugt dadurch einen neuen Schlüssel; Ergebnisse müssen dem
korrekten gespeicherten Termin zugeordnet werden. Eine durchgängige Zuordnung
über stabile Provider-IDs wäre ein weiterer Ausbau.

## Schutzregeln

EV = `p * odds - 1`. Die Filter verwenden ungerundete Werte mit numerischer
Toleranz von 1e-12: EV > 3 % und <= 15 %, Qualität >= 60, Quote <= 8 und
Kombiquote <= 100. Auffälliger EV wird gesperrt, nicht abgeschnitten.
Wahrscheinlichkeiten werden nicht abhängig von der Quote künstlich gedeckelt.
Die Qualitätszahl ist eine erklärte Heuristik und keine kalibrierte Konfidenz.

Im Dashboard können alte Preise mit Hinweisen sichtbar sein. Der Live-Prüfpfad
akzeptiert nur Quoten von The Odds API mit bekanntem, nicht zukünftigem
Zeitstempel und Alter <= 15 Minuten. Auch beim späteren Protokollieren des Scheins
werden Ablaufzeit und Anpfiff geprüft. Ein Speichern im Positionsbuch ist keine
Wettabgabe und garantiert nicht, dass der Anbieter den Preis tatsächlich annimmt.

Kombi-Wahrscheinlichkeiten multiplizieren die Einzelwerte unter einer expliziten
Unabhängigkeitsannahme. Gemeinsam auftretende Risiken sind damit nicht vollständig
modelliert. Einsätze je Schein sind Viertel-Kelly mit 1/1,5/2-%-Grenzen; die
Pro-Einzelansicht verwendet höchstens 1 %. Die Summe mehrerer offener Scheine wird
angezeigt, aber nicht automatisch optimiert oder verhindert.

## Rückblickende Auswertung ohne Informationsleck

Gespeichert werden Modellversion, Wahrscheinlichkeit für alle drei Ausgänge,
Quoten und deren Zeitstempel, verwendete Tabellen einschließlich Saison und
Aktualisierungszeit, erwartete Tore, Datenqualität und damalige Spielbarkeit.
Ein Snapshot-Fingerprint verhindert identische Mehrfachaufnahmen.

Ein Replay berücksichtigt ausschließlich echte Providerprognosen mit
`quote_at <= recorded_at < kickoff` und maximal 24 Stunden alten Quoten. Je
gewähltem Anbieter, Modellversion und Spiel zählt eine Prognose (erste oder letzte).
Das Ergebnis ist ein prospektiv gesammelter Backtest, kein rückwirkendes Training
auf einem historischen Datensatz. Derzeit gibt es kein trainiertes Modell und
daher auch keinen implementierten Walk-forward-Trainingsprozess.

ROI bezieht sich auf einen konstanten Einheitseinsatz je damals freigegebenem
Tipp, ohne Gebühren oder Limits. Kalibrierung, Brier und Log Loss verwenden die
bewertbaren gespeicherten Prognosen. Der Multiclass-Brier summiert drei quadrierte
Fehler (0 bis 2). Die Markt-Baseline normalisiert die inversen Quoten desselben
Anbieters. Nicht abgeschlossene Spiele und die Stichprobengröße bleiben sichtbar.
Ergebnisse werden manuell als bestätigter Endstand erfasst; Korrekturen verändern
die Auswertung, aber niemals die archivierten Prognosen.

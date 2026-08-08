# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-08-08** von `opendata.swiss` und `lindas.admin.ch`.

Ohne Datum ist «gemessen» nach zwei Jahren von «angenommen» nicht mehr
zu unterscheiden — die Datei sieht gleich aus.

## Aufgezeichnet ist die Auswahl, nicht der Datensatz

Die Rohdaten sind zu gross und aendern sich taeglich. Aufgezeichnet ist
deshalb, **welchen Datensatz und welche Ressource jedes Werkzeug
trifft** — und die Kopfzeile der getroffenen Datei. Genau daran hing
der Befund: «die erste CSV» eines Datensatzes mit 26 Ressourcen, davon
18 Code-Listen, ist keine Auswahlregel, sondern eine Wette auf die
Sortierung der Quelle.

## Ohne die Kontrollen belegt nichts davon etwas

| Kontrolle | Antwort | Was sie traegt |
|---|---|---|
| erfundener Pfad unter `lindas.admin.ch` | POST 404 | der 404 auf `/sparql` ist echt |
| erfundene Klasse im fsvo-Namensraum | 0 Instanzen | die foag-Klasse existiert wirklich nicht |

Das Skript bricht ab, wenn eine Kontrolle nicht mehr traegt, wenn eine
gepinnte Ressource verschwindet, wenn eine Kopfzeile leer ist oder mit
einem BOM beginnt, oder wenn einer der Befunde ueberholt ist. Ein
Befund, der still veraltet, ist schlimmer als keiner.

## `datenauswahl.json`

- **Quelle:** `https://opendata.swiss/api/3/action/package_show`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** je Werkzeug der gepinnte Datensatz, die getroffene Ressource und deren Kopfzeile. Die Kopfzeile ist der Gegenstand: Sie trennt Daten von einer Code-Liste. Vorher wurde «die erste CSV» genommen — bei 26 Ressourcen, davon 18 Code-Listen, war das eine Wette auf die Sortierung der Quelle
- **Groesse:** 3324 B
- **SHA-256:** `cff03c75929e67772eb3e7b615c7d6cf9236642479c6c80c0570450cb0c1b959`

## `lindas_endpunkt.json`

- **Quelle:** `https://lindas.admin.ch/…`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** der Abfrage-Endpunkt und die abgefragte Klasse, je mit Kontrolle. Ohne den erfundenen Pfad hiesse der Befund nur «ich bekomme einen 404»; ohne die erfundene Klasse nur «ich bekomme null Zeilen». Erst die Paare zeigen, dass `/sparql` kein Abfrage-Endpunkt ist und die foag-Klasse nicht existiert
- **Groesse:** 658 B
- **SHA-256:** `dbc2dcbff39e2cc9f0b1a2b8ba1432d4bda1327f97083df512ff5295d8e11b47`

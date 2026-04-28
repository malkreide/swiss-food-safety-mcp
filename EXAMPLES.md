# Use Cases & Examples — swiss-food-safety-mcp

Reale Anwendungsfälle nach Zielgruppe. Für dieses MCP werden **keine API-Keys** benötigt. Alle Datenquellen sind öffentlich zugänglich.

## 🏫 Bildung & Schule
Lehrpersonen, Schulbehörden, Fachreferent:innen

### Lebensmittelwarnungen für den Pausenkiosk
«Gibt es aktuell gesundheitsrelevante Lebensmittelrückrufe oder Warnungen des BLV, die Produkte betreffen, welche typischerweise am Pausenkiosk oder in der Schulküche verkauft werden?»

→ `blv_get_public_warnings(limit=10)`
Warum nützlich: Erlaubt Schulverantwortlichen eine proaktive und schnelle Überprüfung, ob aktuelle Rückrufe Auswirkungen auf das eigene schulische Verpflegungsangebot haben.

### Ernährungsgewohnheiten von Kindern im Unterricht
«Wie hoch ist der durchschnittliche tägliche Zuckerkonsum bei Kindern der Altersgruppe '10-12' Jahre laut der aktuellen Schweizer Ernährungsstudie, und wie stark weicht dies von den Empfehlungen ab?»

→ `blv_get_nutrition_data_children(age_group="10-12", nutrient="Zucker")`
Warum nützlich: Liefert Lehrpersonen im Fach Hauswirtschaft oder Natur, Mensch, Gesellschaft (NMG) verlässliche, lokale Schweizer Daten für den Unterricht zum Thema gesunde Ernährung.

## 👨‍👩‍👧 Eltern & Schulgemeinde
Elternräte, interessierte Erziehungsberechtigte

### Pestizide im Schulumfeld
«Welche in der Schweiz zugelassenen Pflanzenschutzmittel enthalten den Wirkstoff 'Glyphosat', über den kürzlich in der Gemeinde im Zusammenhang mit der Grünflächenpflege beim Schulhaus diskutiert wurde?»

→ `blv_search_pesticide_products(active_ingredient="Glyphosat", status="bewilligt")`
Warum nützlich: Bietet besorgten Eltern und Elternräten faktenbasierte und detaillierte Informationen zu umstrittenen Substanzen für sachliche Diskussionen mit der Gemeinde.

### Risikoabschätzung Vogelgrippe bei Ausflügen
«Wurden im letzten Jahr im Kanton Bern Fälle von Vogelgrippe bei Wildvögeln registriert, auf die wir beim Spazieren mit den Kindern am See achten sollten?»

→ `blv_get_avian_influenza(year=2023, canton="BE")`
→ `blv_get_avian_influenza(year=2024, canton="BE")`
Warum nützlich: Hilft Familien dabei, lokale Gesundheitsrisiken durch Tierkrankheiten beim Aufenthalt in der Natur realistisch und evidenzbasiert einzuschätzen.

## 🗳️ Bevölkerung & öffentliches Interesse
Allgemeine Öffentlichkeit, politisch und gesellschaftlich Interessierte

### Kantonale Lebensmittelkontrollen
«Wie haben sich die Beanstandungsquoten bei den kantonalen Lebensmittelkontrollen im Kanton Zürich im Vergleich zum Vorjahr entwickelt?»

→ `blv_get_food_control_results(canton="ZH")`
Warum nützlich: Schafft gesellschaftliche Transparenz über die Wirksamkeit und Ergebnisse der behördlichen Lebensmittelüberwachung in der eigenen Region.

### Antibiotika in der Fleischproduktion
«Wie gross ist die Menge an Antibiotika (in Kilogramm), die letztes Jahr in der Schweizer Schweine- und Geflügelmast eingesetzt wurde?»

→ `blv_get_antibiotic_usage_vet(animal_species="Schwein")`
→ `blv_get_antibiotic_usage_vet(animal_species="Geflügel")`
Warum nützlich: Informiert Konsumentinnen und Konsumenten fundiert über den tatsächlichen Medikamenteneinsatz in der landwirtschaftlichen Tierproduktion und unterstützt bewusste Kaufentscheidungen.

## 🤖 KI-Interessierte & Entwickler:innen
MCP-Enthusiast:innen, Forscher:innen, Prompt Engineers, öffentliche Verwaltung

### Tierseuchen vs. Bevölkerungsdichte (Multi-Server)
«Welche meldepflichtigen Tierseuchen traten 2023 im Kanton Zürich auf, und wie verhält sich diese Verteilung im Vergleich zu soziodemografischen Faktoren in den betroffenen Gemeinden?»

→ `blv_search_animal_diseases(canton="ZH", year_from=2023, year_to=2023)` (swiss-food-safety-mcp)
→ `get_population_statistics(canton="ZH", year=2023)` ([swiss-statistics-mcp](https://github.com/malkreide/swiss-statistics-mcp))
Warum nützlich: Demonstriert eindrücklich, wie kantonale veterinärmedizinische Risikodaten des BLV mit demografischen Daten aus dem Statistik-Server für komplexe, raumbezogene Risikoanalysen verknüpft werden können.

### Explorative Datenanalyse
«Welche offenen Datensätze bietet das BLV zum Thema Fleischuntersuchung an, und wie lautet die URL zum JSON-Ressourcendownload des relevantesten Treffers?»

→ `blv_list_datasets(search="fleischuntersuchung")`
→ `blv_get_dataset_info(dataset_name="fleischuntersuchung-schlachttier-kontrolle")`
Warum nützlich: Ermöglicht Data Scientists und Forschenden das automatisierte, API-gesteuerte Auffinden und Extrahieren von Strukturdaten aus der CKAN-API von opendata.swiss.

---

## 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|-------------|---------|-------------|
| Aktuelle Lebensmittelrückrufe und Gesundheitswarnungen abfragen | `blv_get_public_warnings` | Nein |
| Historische Ausbrüche von Tierseuchen in meinem Kanton analysieren | `blv_search_animal_diseases` | Nein |
| Vogelgrippefälle bei Wildvögeln auf einer Karte verorten | `blv_get_avian_influenza` | Nein |
| Resultate der kantonalen Lebensmittelinspektionen einsehen | `blv_get_food_control_results` | Nein |
| Den Antibiotikaeinsatz bei Haus- und Nutztieren überprüfen | `blv_get_antibiotic_usage_vet` | Nein |
| Reale Ernährungsdaten von Schweizer Schulkindern auswerten | `blv_get_nutrition_data_children` | Nein |
| Ein bestimmtes Pflanzenschutzmittel im Zulassungsregister suchen | `blv_search_pesticide_products` | Nein |
| Den gesamten BLV-Datenkatalog auf opendata.swiss durchforsten | `blv_list_datasets`, `blv_get_dataset_info` | Nein |

# SessionStart-Hook: Klon-Aktualitaet

`session-start.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `origin/<Default-Branch>` liegt. Liegt er nicht
zurueck, sagt der Hook nichts.

Registriert ist er in `.claude/settings.json` (dort steht kein Kommentar —
`settings.json` wird als striktes JSON gelesen, ein `//` daneben macht die
Datei unlesbar und damit den Hook wirkungslos).

## Warum es diesen Hook gibt

Ein veralteter Klon hat am 3.8.2026 **zweimal** eine rote CI erzeugt, deren
Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau die,
die das Gate einfuehrten, an dem der Branch scheiterte. Man sucht den Fehler
dann in den Dateien, die man selbst geaendert hat, und findet dort nichts,
weil dort nichts ist.

Die Pruefung kostet eine Sekunde und ersetzt eine Fehlersuche in den falschen
Dateien.

## Was er garantiert

**Er blockiert die Session nie.** Das ist die oberste Zusicherung, wichtiger
als jede Meldung: Ein Hook, der bei Netzproblemen die Arbeit anhaelt, wird
nach dem zweiten Mal abgeschaltet und schuetzt danach gar nichts. Still mit
Exit 0 enden deshalb alle diese Faelle:

| Fall | Verhalten |
| --- | --- |
| Kein Git-Repo / kein `origin` | still, Exit 0 |
| Kein Netz, DNS haengt, Remote weg | still, Exit 0 (nach hoechstens `CLAUDE_FRESHNESS_TIMEOUT`, Standard 5 s) |
| Fehlende Credentials | still, Exit 0 — Git fragt nie interaktiv (`GIT_TERMINAL_PROMPT=0`, `ssh -oBatchMode=yes`) |
| Default-Branch nicht ermittelbar | still, Exit 0 — lieber schweigen als gegen einen geratenen Branch vergleichen |
| Detached HEAD | vergleicht normal weiter; `HEAD..FETCH_HEAD` ist auch dort definiert |
| Rueckstand 0 | still, Exit 0 |

Im Skript steht bewusst **kein** `set -e` und kein `pipefail`: ein Abbruch
mitten im Skript waere genau das Blockieren, das hier ausgeschlossen ist.
Jeder Schritt prueft stattdessen selbst und faellt auf `exit 0` zurueck.

## Der Default-Branch wird ermittelt, nicht angenommen

Nicht `main` raten: Drei Server im Portfolio (`openlex-mcp`, `swiss-courts-mcp`,
`swisstopo-mcp`) heissen ihren Standard-Branch `master`. Genau diese Annahme
hat schon einmal einen Branch 15 Commits alt werden lassen — verglichen wurde
gegen einen Branch, den es nicht gab, und das Ergebnis war unauffaellig.

Der Hook nimmt zuerst den lokalen Symref `refs/remotes/origin/HEAD` (kostet
kein Netz) und faellt auf `git ls-remote --symref origin HEAD` zurueck.

## Timeout

`git fetch` laeuft unter `timeout` (Standard 5 s, ueberschreibbar per
`CLAUDE_FRESHNESS_TIMEOUT`). Fehlt `timeout` auf dem Host, bremst
`http.lowSpeedLimit`/`lowSpeedTime` — schwaecher, aber vorhanden. Der
`timeout: 15` in `settings.json` ist die zweite Reissleine darueber.

## Selbst ausprobieren

```bash
CLAUDE_PROJECT_DIR="$PWD" .claude/hooks/session-start.sh
```

Getestet wird das Verhalten in `tests/test_session_start_hook.py` gegen echte
Wegwerf-Repositories — nicht gegen Attrappen.

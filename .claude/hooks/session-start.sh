#!/usr/bin/env bash
# SessionStart-Hook — Klon-Aktualitaet.
#
# Meldet beim Sessionstart, wie viele Commits der ausgecheckte Stand hinter
# origin/<Default-Branch> liegt. Bei 0 schweigt er.
#
# GRUND: Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt,
# deren Ursache nicht im Diff stand — die fehlenden Commits waren jeweils
# genau die, die das Gate einfuehrten, an dem der Branch scheiterte. Die
# Pruefung kostet eine Sekunde und ersetzt eine Fehlersuche in den falschen
# Dateien.
#
# HARTE REGEL, wichtiger als jede Meldung: Dieser Hook blockiert die Session
# nie. Kein Netz, kein Remote, kein Git-Repo, detached HEAD, flatterndes DNS,
# fehlende Credentials — jeder dieser Faelle endet still mit Exit 0. Ein Hook,
# der bei Netzproblemen die Arbeit anhaelt, wird nach dem zweiten Mal
# abgeschaltet und schuetzt danach gar nichts.
#
# Deshalb ausdruecklich KEIN `set -e` und kein `pipefail`: ein Abbruch mitten
# im Skript waere genau das Blockieren, das hier ausgeschlossen ist. Jeder
# Schritt wird stattdessen einzeln geprueft und faellt auf `exit 0` zurueck.

# Sekunden, die das fetch hoechstens kosten darf. Kurz genug, dass der
# Sessionstart nicht spuerbar haengt.
FETCH_TIMEOUT="${CLAUDE_FRESHNESS_TIMEOUT:-5}"

# Git darf unter keinen Umstaenden interaktiv nachfragen — ein Prompt auf
# Zugangsdaten haengt bis zum Timeout des Hosts, nicht bis zu unserem.
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true
export SSH_ASKPASS=/bin/true
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -oBatchMode=yes -oConnectTimeout=${FETCH_TIMEOUT}}"

# `timeout` deckelt die Wanduhr hart. Fehlt es (z. B. macOS ohne coreutils),
# bleibt der Git-eigene Low-Speed-Abbruch als schwaechere, aber vorhandene
# Bremse. Ohne diesen Zweig waere der Hook auf solchen Hosts unbegrenzt.
_git_kurz() {
    if command -v timeout >/dev/null 2>&1; then
        timeout "$FETCH_TIMEOUT" git "$@"
    else
        git -c "http.lowSpeedLimit=1000" -c "http.lowSpeedTime=$FETCH_TIMEOUT" "$@"
    fi
}

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

# Kein Repo, kein Remote — nichts zu vergleichen, nichts zu melden.
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0

# Default-Branch ermitteln, NICHT `main` annehmen: drei Server im Portfolio
# heissen ihn `master`, und genau diese Annahme hat schon einmal einen Branch
# 15 Commits alt werden lassen. Erst der lokale Symref (kostet kein Netz),
# dann als Rueckfall die Frage an den Remote.
zweig=""
if symref=$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null); then
    zweig="${symref#refs/remotes/origin/}"
fi
if [ -z "$zweig" ]; then
    zweig=$(_git_kurz ls-remote --symref origin HEAD 2>/dev/null |
        sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p' | head -n 1)
fi
# Leer heisst: nicht ermittelbar. Dann lieber schweigen als gegen einen
# geratenen Branch vergleichen und eine falsche Zahl melden.
[ -n "$zweig" ] || exit 0
[ "$zweig" != "HEAD" ] || exit 0

_git_kurz fetch --quiet origin "$zweig" >/dev/null 2>&1 || exit 0

# FETCH_HEAD statt origin/<zweig>: nur FETCH_HEAD ist nach genau diesem fetch
# garantiert gesetzt, unabhaengig von der Refspec-Konfiguration des Klons.
rueckstand=$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null) || exit 0
case "$rueckstand" in
    '' | *[!0-9]*) exit 0 ;;
esac
[ "$rueckstand" -gt 0 ] || exit 0

_json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

if [ "$rueckstand" -eq 1 ]; then
    _commits="1 Commit"
else
    _commits="$rueckstand Commits"
fi

meldung="Klon-Aktualitaet: Der ausgecheckte Stand liegt $_commits hinter origin/$zweig."
meldung="$meldung Vor der Arbeit aktualisieren: git fetch origin $zweig && git merge --ff-only FETCH_HEAD"
meldung="$meldung (oder rebase). Grund: Fehlende Commits sind erfahrungsgemaess genau die, die ein"
meldung="$meldung CI-Gate einfuehren — die rote CI zeigt dann auf Dateien, die der Diff nie angefasst hat."

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' \
    "$(_json_escape "$meldung")"

exit 0

"""Der SessionStart-Hook meldet Rueckstand — und blockiert nie.

Geprueft wird gegen echte Wegwerf-Repositories, nicht gegen Attrappen: ein
handgeschriebenes Fake-Git kodiert die Annahme des Autors darueber, was git
tut, und kann sie deshalb nicht widerlegen. Die einzige Ausnahme ist der
Timeout-Test, der ein haengendes `git fetch` braucht — das laesst sich mit
einem echten Remote nicht verlaesslich herstellen.

Der Default-Branch der Test-Repos heisst absichtlich `master`, nicht `main`:
Ein Hook, der `main` fest verdrahtet, ist gegen ein `main`-Repo nicht von
einem korrekten zu unterscheiden. Drei Server im Portfolio heissen ihren
Standard-Branch `master`, und genau diese Annahme hat schon einmal einen
Branch 15 Commits alt werden lassen.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_HOOK = _ROOT / ".claude" / "hooks" / "session-start.sh"
_SETTINGS = _ROOT / ".claude" / "settings.json"

# Der Default-Branch der Testrepos. Bewusst nicht `main` — siehe Modul-Docstring.
_DEFAULT_BRANCH = "master"

# Ohne Identitaet verweigert git den Commit, und ohne diese Kappung erbt der
# Test die ~/.gitconfig des laufenden Systems (Hooks, Templates, Aliase).
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def _git(pfad: pathlib.Path, *args: str) -> str:
    ergebnis = subprocess.run(
        ["git", *args],
        cwd=pfad,
        env={**os.environ, **_GIT_ENV},
        capture_output=True,
        text=True,
        check=True,
    )
    return ergebnis.stdout.strip()


def _commit(pfad: pathlib.Path, text: str) -> None:
    (pfad / "datei.txt").write_text(text, encoding="utf-8")
    _git(pfad, "add", "datei.txt")
    _git(pfad, "commit", "-m", text)


def _hook_lauf(
    projekt: pathlib.Path,
    *,
    timeout_s: str = "5",
    pfad_prefix: pathlib.Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Fuehrt den Hook so aus, wie Claude Code ihn ausfuehrt."""
    umgebung = {
        **os.environ,
        **_GIT_ENV,
        "CLAUDE_PROJECT_DIR": str(projekt),
        "CLAUDE_FRESHNESS_TIMEOUT": timeout_s,
    }
    if pfad_prefix is not None:
        umgebung["PATH"] = f"{pfad_prefix}{os.pathsep}{os.environ['PATH']}"
    return subprocess.run(
        [str(_HOOK)],
        # Ein anderes cwd als das Projekt: Der Hook muss sich auf
        # CLAUDE_PROJECT_DIR verlassen, nicht darauf, zufaellig richtig zu stehen.
        cwd=str(projekt.parent),
        env=umgebung,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture
def klon(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """Ein Remote auf `master` und ein frischer, aktueller Klon davon."""
    remote = tmp_path / "remote"
    remote.mkdir()
    _git(remote, "init", "--quiet", "--initial-branch", _DEFAULT_BRANCH)
    _commit(remote, "erster")
    # Ohne das verweigert das Remote den push auf den ausgecheckten Branch.
    _git(remote, "config", "receive.denyCurrentBranch", "ignore")

    ziel = tmp_path / "klon"
    _git(tmp_path, "clone", "--quiet", str(remote), str(ziel))
    return remote, ziel


def _meldung(ergebnis: subprocess.CompletedProcess[str]) -> str:
    """Der additionalContext aus der Hook-Ausgabe."""
    nutzlast = json.loads(ergebnis.stdout)
    spezifisch = nutzlast["hookSpecificOutput"]
    assert spezifisch["hookEventName"] == "SessionStart"
    return spezifisch["additionalContext"]


def test_meldet_rueckstand_mit_zahl_und_branch(klon) -> None:
    remote, ziel = klon
    _commit(remote, "zweiter")
    _commit(remote, "dritter")

    ergebnis = _hook_lauf(ziel)

    assert ergebnis.returncode == 0
    meldung = _meldung(ergebnis)
    assert "2 Commits" in meldung
    # Der Branchname gehoert in die Meldung: `main` hier waere die Annahme,
    # die dieser Test gerade widerlegen soll.
    assert f"origin/{_DEFAULT_BRANCH}" in meldung
    assert "main" not in meldung


def test_einzahl_bei_genau_einem_commit(klon) -> None:
    remote, ziel = klon
    _commit(remote, "zweiter")

    meldung = _meldung(_hook_lauf(ziel))
    assert "1 Commit hinter" in meldung


def test_schweigt_wenn_aktuell(klon) -> None:
    _, ziel = klon

    ergebnis = _hook_lauf(ziel)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout == ""


def test_default_branch_auch_ohne_lokalen_symref(klon) -> None:
    """Fehlt `refs/remotes/origin/HEAD`, wird der Remote gefragt — nicht geraten.

    Ein flach oder mit `--single-branch` erzeugter Klon hat diesen Symref nicht.
    Ohne den Rueckfall auf `ls-remote --symref` faellt der Hook hier still aus
    und meldet nie wieder etwas — der Ausfall waere unsichtbar.
    """
    remote, ziel = klon
    _git(ziel, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    _commit(remote, "zweiter")

    meldung = _meldung(_hook_lauf(ziel))
    assert f"origin/{_DEFAULT_BRANCH}" in meldung


def test_detached_head_wird_verglichen_statt_zu_scheitern(klon) -> None:
    remote, ziel = klon
    _commit(remote, "zweiter")
    _git(ziel, "checkout", "--quiet", "--detach", "HEAD")

    ergebnis = _hook_lauf(ziel)

    assert ergebnis.returncode == 0
    assert "1 Commit hinter" in _meldung(ergebnis)


def test_unerreichbarer_remote_blockiert_nicht(klon) -> None:
    remote, ziel = klon
    _commit(remote, "zweiter")
    _git(ziel, "remote", "set-url", "origin", "/gibt/es/nicht/remote.git")
    # Auch der lokale Symref muss weg, sonst faellt der Hook nicht auf den
    # Remote zurueck und der Test prueft die falsche Stelle.
    _git(ziel, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")

    ergebnis = _hook_lauf(ziel)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout == ""


def test_kein_remote_blockiert_nicht(klon) -> None:
    _, ziel = klon
    _git(ziel, "remote", "remove", "origin")

    ergebnis = _hook_lauf(ziel)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout == ""


def test_kein_git_repo_blockiert_nicht(tmp_path: pathlib.Path) -> None:
    schlicht = tmp_path / "kein_repo"
    schlicht.mkdir()

    ergebnis = _hook_lauf(schlicht)

    assert ergebnis.returncode == 0
    assert ergebnis.stdout == ""


def test_haengendes_fetch_wird_abgebrochen(klon, tmp_path: pathlib.Path) -> None:
    """Ein fetch, das nie zurueckkommt, haelt den Sessionstart nicht auf.

    Das ist der einzige Punkt, an dem ein echter Remote nicht taugt: ein
    haengendes Netz laesst sich nicht reproduzierbar herstellen. Der Ersatz
    haengt nur beim `fetch` und reicht jedes andere git-Kommando unveraendert
    an das echte git weiter — die uebrige Mechanik bleibt also echt.
    """
    remote, ziel = klon
    _commit(remote, "zweiter")

    echtes_git = subprocess.run(["which", "git"], capture_output=True, text=True, check=True)
    attrappe = tmp_path / "bin"
    attrappe.mkdir()
    (attrappe / "git").write_text(
        "#!/bin/sh\n"
        # Nicht nur $1 pruefen: ohne `timeout` ruft der Hook
        # `git -c http.lowSpeedLimit=... fetch` auf, dort steht `-c` an $1.
        'for a in "$@"; do [ "$a" = "fetch" ] && { sleep 60; exit 0; }; done\n'
        f'exec {echtes_git.stdout.strip()} "$@"\n',
        encoding="utf-8",
    )
    (attrappe / "git").chmod(0o755)

    beginn = time.monotonic()
    ergebnis = _hook_lauf(ziel, timeout_s="2", pfad_prefix=attrappe)
    dauer = time.monotonic() - beginn

    assert ergebnis.returncode == 0
    assert ergebnis.stdout == ""
    # Deutlich unter den 60 s der Attrappe: der Abbruch kam vom Timeout,
    # nicht daher, dass der Schlaf zufaellig endete.
    assert dauer < 30


def test_hook_ist_registriert_und_ausfuehrbar() -> None:
    """Ein umbenanntes Skript macht die settings.json still wirkungslos."""
    assert os.access(_HOOK, os.X_OK)

    konfiguration = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    befehle = [
        eintrag["command"]
        for gruppe in konfiguration["hooks"]["SessionStart"]
        for eintrag in gruppe["hooks"]
    ]
    assert any(befehl.endswith(f"/{_HOOK.name}") for befehl in befehle), befehle

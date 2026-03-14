"""battle_log.py — file-based technical battle logger for Fabled.

Writes every game-visible log entry PLUS extra technical details
(damage formula steps, HP changes, stat values, status ticks, etc.)
to battle_log.txt in the user's Saved Games folder. Overwritten each battle.
"""
import datetime
import os

_f = None


def _log_path() -> str:
    """Return the path for battle_log.txt under the per-user Saved Games folder."""
    home = os.path.expanduser("~")
    base = os.path.join(home, "Saved Games", "Fabled")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "battle_log.txt")


def init():
    """Open battle_log.txt for writing (overwrites previous log)."""
    global _f
    if _f:
        try:
            _f.close()
        except Exception:
            pass
    path = _log_path()
    _f = open(path, "w", encoding="utf-8", buffering=1)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _w("=" * 70)
    _w(f"FABLED BATTLE LOG  —  {ts}")
    _w("=" * 70)
    _w("")


def _w(s: str):
    if _f:
        _f.write(s + "\n")
        _f.flush()


def log(s: str):
    """Mirror a game-visible log entry to the file."""
    _w(s)


def tech(s: str):
    """Write a technical detail line (not shown in-game)."""
    _w("    [T] " + s)


def section(s: str):
    """Write a section separator."""
    _w("")
    _w("─" * 60)
    _w(s)
    _w("─" * 60)


def close():
    global _f
    if _f:
        try:
            _f.close()
        except Exception:
            pass
        _f = None

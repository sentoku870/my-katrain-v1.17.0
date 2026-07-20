"""Phase 280 i18n cleanup: remove obsolete AI strategy entries.

Removes ``ai:*`` and ``aihelp:*`` translations for strategies that no
longer exist after the AI strategy slim-down. Survivors:
  - ai:default / aihelp:default
  - ai:handicap / aihelp:handicap

Also removes the following setup-position entries (Phase 280-B):
  - setupposition
  - setup position explanation
  - setup position black score
  - setup position move number
  - setup game status message
"""

from __future__ import annotations

from pathlib import Path

import polib

OBSOLETE_AI_MSGIDS = [
    "ai:jigo",
    "ai:scoreloss",
    "ai:policy",
    "ai:p:weighted",
    "ai:p:pick",
    "ai:p:local",
    "ai:p:tenuki",
    "ai:p:influence",
    "ai:p:territory",
    "ai:p:rank",
    "ai:simple",
    "ai:antimirror",
    "ai:human",
    "ai:pro",
]
OBSOLETE_AIHELP_MSGIDS = [msgid.replace("ai:", "aihelp:") for msgid in OBSOLETE_AI_MSGIDS]

OBSOLETE_SETUP_MSGIDS = [
    "setupposition",
    "setup position explanation",
    "setup position black score",
    "setup position move number",
    "setup game status message",
]

ALL_OBSOLETE_MSGIDS = set(OBSOLETE_AI_MSGIDS + OBSOLETE_AIHELP_MSGIDS + OBSOLETE_SETUP_MSGIDS)


def remove_obsolete(po_path: Path) -> int:
    po = polib.pofile(str(po_path))
    initial = len(po)
    po[:] = [entry for entry in po if entry.msgid not in ALL_OBSOLETE_MSGIDS]
    removed = initial - len(po)
    po.save(str(po_path))
    mo_path = po_path.with_suffix(".mo")
    po.save_as_mofile(str(mo_path))
    return removed


def main() -> None:
    i18n_root = Path("katrain/i18n/locales")
    for locale in ("jp", "en"):
        po_path = i18n_root / locale / "LC_MESSAGES" / "katrain.po"
        removed = remove_obsolete(po_path)
        print(f"{locale}: removed {removed} obsolete entries from {po_path}")


if __name__ == "__main__":
    main()

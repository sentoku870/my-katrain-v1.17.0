"""Phase 272-B: Add 7 missing i18n keys to en/jp .po and compile .mo.

Adding 7 msgid entries that are referenced in code but missing from .po files:
1. "Bug report saved to:\n%s"              (diagnostics_popup.py:363)
2. "Copied!"                                 (diagnostics_popup.py:318)
3. "Copy Info"                               (diagnostics_popup.py:100)
4. "Failed to generate bug report:\n%s"     (diagnostics_popup.py:409)
5. "Failed to save karte:\n{error}"          (karte_export.py:317)
6. "Mistake played (sound disabled)"        (__main__.py:667)
7. "Summary exported"                        (summary_io.py:272)

Note: These are English phrases used as msgid, which technically violates the
i18n-workflow "key-style only" convention. However, this matches the existing
precedent in the .po file (e.g. "Cancel", "Close", "Best move: {move}") and
renaming would require a much larger refactor. Adding as-is keeps scope
manageable.
"""

import polib

# (msgid, en_msgstr, jp_msgstr)
ENTRIES = [
    (
        "Bug report saved to:\\n%s",
        "Bug report saved to:\n%s",
        "バグレポートを保存しました:\n%s",
    ),
    (
        "Copied!",
        "Copied!",
        "コピーしました!",
    ),
    (
        "Copy Info",
        "Copy Info",
        "情報をコピー",
    ),
    (
        "Failed to generate bug report:\\n%s",
        "Failed to generate bug report:\n%s",
        "バグレポートの生成に失敗しました:\n%s",
    ),
    (
        "Failed to save karte:\\n{error}",
        "Failed to save karte:\n{error}",
        "カルテの保存に失敗しました:\n{error}",
    ),
    (
        "Mistake played (sound disabled)",
        "Mistake played (sound disabled)",
        "悪手を打ちました (サウンドオフ)",
    ),
    (
        "Summary exported",
        "Summary exported",
        "サマリをエクスポートしました",
    ),
]

PO_FILES = {
    "en": "katrain/i18n/locales/en/LC_MESSAGES/katrain.po",
    "jp": "katrain/i18n/locales/jp/LC_MESSAGES/katrain.po",
}

# Note: polib escapes \n in msgid/msgstr automatically. The msgid
# "Bug report saved to:\n%s" in Python source is stored as
# "Bug report saved to:\\n%s" in .po file, so we use the escaped form here.

for lang, path in PO_FILES.items():
    po = polib.pofile(path)
    existing_msgids = {entry.msgid for entry in po}
    added = 0
    for msgid, en_str, jp_str in ENTRIES:
        # polib stores the un-escaped form in entry.msgid
        target_msgid = msgid.replace("\\n", "\n")
        if target_msgid in existing_msgids:
            print(f"  [{lang}] already exists: {target_msgid!r}")
            continue
        # Build a new entry
        entry = polib.POEntry(
            msgid=target_msgid,
            msgstr=en_str if lang == "en" else jp_str,
        )
        po.append(entry)
        added += 1
        print(f"  [{lang}] added: {target_msgid!r}")
    if added > 0:
        po.save(path)
        # Compile .mo
        po.save_as_mofile(path.replace(".po", ".mo"))
        print(f"  [{lang}] compiled .mo (added {added} entries)")
    else:
        print(f"  [{lang}] no changes needed")

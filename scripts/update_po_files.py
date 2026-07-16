
"""Phase 95+ helper script: append the legacy Karte Export i18n keys to
the en/jp PO files. Originally hard-coded to the Windows-only path
``d:\\github\\katrain-1.17.0\\...`` which broke for Linux / WSL users.

This script is kept as a developer convenience only; the canonical
workflow is described in ``docs/i18n-workflow.md`` and uses the
``polib`` module via ``python -m polib`` instead.
"""

from __future__ import annotations

from pathlib import Path

# Resolve relative to this script so the same code works from any
# checkout path (Windows, WSL, or Linux).
REPO_ROOT = Path(__file__).resolve().parent.parent
jp_file = str(REPO_ROOT / "katrain" / "i18n" / "locales" / "jp" / "LC_MESSAGES" / "katrain.po")
en_file = str(REPO_ROOT / "katrain" / "i18n" / "locales" / "en" / "LC_MESSAGES" / "katrain.po")

new_keys_jp = """
# Common UI
msgid "Error"
msgstr "エラー"

msgid "Warning"
msgstr "警告"

msgid "OK"
msgstr "OK"

msgid "Save"
msgstr "保存"

msgid "Cancel"
msgstr "キャンセル"

msgid "Browse..."
msgstr "参照..."

# Karte Export
msgid "mykatrain:export-karte:success-title"
msgstr "カルテ出力完了"

msgid "mykatrain:export-karte:success-msg"
msgstr "以下に保存しました：\\n{files}"

msgid "mykatrain:clipboard-copy"
msgstr "パスをコピー"

msgid "mykatrain:clipboard-copied"
msgstr "コピーしました！"
"""

new_keys_en = """
# Common UI
msgid "Error"
msgstr "Error"

msgid "Warning"
msgstr "Warning"

msgid "OK"
msgstr "OK"

msgid "Save"
msgstr "Save"

msgid "Cancel"
msgstr "Cancel"

msgid "Browse..."
msgstr "Browse..."

# Karte Export
msgid "mykatrain:export-karte:success-title"
msgstr "Karte Exported"

msgid "mykatrain:export-karte:success-msg"
msgstr "Saved to:\\n{files}"

msgid "mykatrain:clipboard-copy"
msgstr "Copy path"

msgid "mykatrain:clipboard-copied"
msgstr "Copied!"
"""

def append_keys(file_path, content):
    with open(file_path, encoding='utf-8') as f:
        current = f.read()

    if 'msgid "Error"' in current:
        print(f"Skipping {file_path}: Keys already seem to exist.")
        return

    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(content)
    print(f"Appended keys to {file_path}")

if __name__ == "__main__":
    try:
        append_keys(jp_file, new_keys_jp)
        append_keys(en_file, new_keys_en)
    except Exception as e:
        print(f"Error: {e}")

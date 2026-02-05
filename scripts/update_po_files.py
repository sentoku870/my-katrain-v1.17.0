
import os

jp_file = r'd:\github\katrain-1.17.0\katrain\i18n\locales\jp\LC_MESSAGES\katrain.po'
en_file = r'd:\github\katrain-1.17.0\katrain\i18n\locales\en\LC_MESSAGES\katrain.po'

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
    with open(file_path, 'r', encoding='utf-8') as f:
        current = f.read()
    
    if 'msgid "Error"' in current:
        print(f"Skipping {file_path}: Keys already seem to exist.")
        return

    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(content)
    print(f"Appended keys to {file_path}")

try:
    append_keys(jp_file, new_keys_jp)
    append_keys(en_file, new_keys_en)
except Exception as e:
    print(f"Error: {e}")

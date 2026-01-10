# i18n Workflow - myKatrain Translation Guide

> **Single Source of Truth for i18n in myKatrain**
> Last updated: 2026-01-03

---

## Golden Rules

1. **msgid = key-style, msgstr = human-readable**
   - `msgid "menu:save"` → `msgstr "Save Game"`
   - English (`en` locale) is **NOT** bypassed—it uses `.po`/`.mo` like other languages
   - **Never** use raw English phrases as msgid (e.g., `msgid "Save Game"` is wrong)

2. **Locale code: `jp` for Japanese** (not `ja`)
   - Confirmed in `katrain/i18n/locales/jp/`
   - Supported locales: `en`, `jp` only (other locales have been removed)
   - Note: `jp` is the directory name used in this repo (not ISO `ja`)

3. **Always compile `.mo` after editing `.po`**
   - `.po` files are source (human-editable)
   - `.mo` files are binary (runtime)
   - **UI reads `.mo` only**—`.po` changes have no effect until compiled

4. **Python code: `i18n._("key")`**
   - Example: `i18n._("menu:save")`

5. **Kivy/KV code: `i18n._("key")`**
   - Example: `text: i18n._("menu:save")`
   - Dynamic binding: `lang_change_tracking: i18n._('')` triggers re-translation

6. **i18n.py script auto-fixes missing translations**
   - Run `python i18n.py -todo` to:
     - Detect missing msgids in other locales
     - Auto-add from `en` locale as fallback
     - Compile all `.mo` files
   - **Exit code 1** if changes were made (normal in CI)

7. **Windows: Force UTF-8 encoding**
   - PowerShell: `$env:PYTHONUTF8 = "1"`
   - Or use `-Encoding UTF8` in file operations

---

## Step-by-Step: Adding a New UI String

### A. Python (.py) Code

#### 1. Add the translation call

```python
# In katrain/__main__.py or other .py file
from katrain.core.lang import i18n

# Before
self.show_message("Feature completed")

# After
self.show_message(i18n._("mykatrain:feature:completed"))
```

#### 2. Add to English `.po` file

Edit `katrain/i18n/locales/en/LC_MESSAGES/katrain.po`:

```po
msgid "mykatrain:feature:completed"
msgstr "Feature completed"
```

**Naming convention**:
- Format: `namespace:category:key`
- Examples:
  - `menu:save` (main menu)
  - `ai:p:influence` (AI settings)
  - `mykatrain:batch:title` (myKatrain additions)

#### 3. Add to Japanese `.po` file

Edit `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po`:

```po
msgid "mykatrain:feature:completed"
msgstr "機能が完了しました"
```

#### 4. Compile `.mo` files

```powershell
# PowerShell (Windows 11)
$env:PYTHONUTF8 = "1"
python -c "import sys; sys.path.insert(0, 'C:/Users/mono_/AppData/Local/Programs/Python/Python310/Tools/i18n'); import msgfmt; msgfmt.make('katrain/i18n/locales/en/LC_MESSAGES/katrain.po', 'katrain/i18n/locales/en/LC_MESSAGES/katrain.mo')"
python -c "import sys; sys.path.insert(0, 'C:/Users/mono_/AppData/Local/Programs/Python/Python310/Tools/i18n'); import msgfmt; msgfmt.make('katrain/i18n/locales/jp/LC_MESSAGES/katrain.po', 'katrain/i18n/locales/jp/LC_MESSAGES/katrain.mo')"
```

**Or use i18n.py** (recommended):

```powershell
$env:PYTHONUTF8 = "1"
python i18n.py
```

This will:
- Auto-add missing msgids to all supported locales
- Compile all `.mo` files automatically

#### 5. Verify in app

```powershell
python -m katrain
```

- Switch language: Settings → Language → Japanese
- Check that the string displays correctly

---

### B. Kivy (.kv) Code

#### 1. Add the translation call in `.kv` file

Edit `katrain/gui.kv` or other `.kv` file:

```kv
# Before
Button:
    text: "Save Game"

# After
Button:
    text: i18n._("menu:save")
```

**Important for dynamic updates**:

```kv
<MyWidget>:
    lang_change_tracking: i18n._('')  # Triggers re-translation on lang change
    Label:
        text: i18n._("menu:save")
```

#### 2-5. Same as Python case

Follow steps 2-5 from section A (add to `.po`, compile `.mo`, verify).

---

## Copy-Pastable PowerShell Commands

### Setup (one-time)

```powershell
# Set UTF-8 encoding for current session
$env:PYTHONUTF8 = "1"
$OutputEncoding = [System.Text.Encoding]::UTF8
```

### Compile .mo files (EN + JP only)

```powershell
# English
python -c "import sys; sys.path.insert(0, 'C:/Users/mono_/AppData/Local/Programs/Python/Python310/Tools/i18n'); import msgfmt; msgfmt.make('katrain/i18n/locales/en/LC_MESSAGES/katrain.po', 'katrain/i18n/locales/en/LC_MESSAGES/katrain.mo')"

# Japanese
python -c "import sys; sys.path.insert(0, 'C:/Users/mono_/AppData/Local/Programs/Python/Python310/Tools/i18n'); import msgfmt; msgfmt.make('katrain/i18n/locales/jp/LC_MESSAGES/katrain.po', 'katrain/i18n/locales/jp/LC_MESSAGES/katrain.mo')"
```

### Compile all locales + auto-fix missing translations

```powershell
python i18n.py
```

### Check for missing msgids

```powershell
# Search Python code for i18n._() calls
Select-String -Path "katrain\**\*.py" -Pattern 'i18n\._\([''"]([^''"]+)[''"]\)' | Select-Object -ExpandProperty Matches | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique

# Search KV code for i18n._() calls
Select-String -Path "katrain\**\*.kv" -Pattern 'i18n\._\([''"]([^''"]+)[''"]\)' | Select-Object -ExpandProperty Matches | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
```

### Quick check: Search for raw keys in .po

```powershell
# Find msgids not translated in Japanese
Select-String -Path "katrain\i18n\locales\jp\LC_MESSAGES\katrain.po" -Pattern 'msgstr ""$' -Context 1,0
```

---

## Troubleshooting

### Problem 1: UI shows raw key like `mykatrain:batch:title`

**Likely causes**:
1. `.mo` file not regenerated after `.po` edit
2. Wrong locale loaded (check Settings → Language)
3. msgid exists in `.po` but msgstr is empty

**Fixes**:
```powershell
# 1. Recompile .mo
python i18n.py

# 2. Check .po file
cat katrain/i18n/locales/en/LC_MESSAGES/katrain.po | Select-String -Pattern "mykatrain:batch:title" -Context 0,1

# 3. Verify msgstr is not empty
# If msgstr is "", add the translation and recompile
```

---

### Problem 2: Japanese not applied (shows English instead)

**Likely causes**:
1. msgid missing in `jp/LC_MESSAGES/katrain.po`
2. `.mo` file not regenerated
3. Fallback to `en` locale due to encoding error

**Fixes**:
```powershell
# 1. Check if msgid exists in JP .po
cat katrain/i18n/locales/jp/LC_MESSAGES/katrain.po | Select-String -Pattern "mykatrain:batch:title" -Context 0,1

# 2. If missing, add manually or run i18n.py
python i18n.py  # Auto-adds from en locale

# 3. Force UTF-8 and recompile
$env:PYTHONUTF8 = "1"
python i18n.py
```

---

### Problem 3: KV string not translated

**Likely causes**:
1. Missing `lang_change_tracking: i18n._('')` in widget
2. Syntax error in `.kv` file (e.g., missing quotes)
3. `.mo` file not regenerated

**Fixes**:
```kv
# Add lang_change_tracking to parent widget
<MyWidget>:
    lang_change_tracking: i18n._('')  # ← Add this
    Label:
        text: i18n._("menu:save")
```

```powershell
# Recompile .mo
python i18n.py

# Restart app
python -m katrain
```

---

### Problem 4: i18n.py exits with code 1 in CI

**This is normal!**

- `i18n.py` auto-fixes missing translations by:
  - Copying msgids from `en` to other locales
  - Compiling all `.mo` files
- Exit code 1 means "changes were made"
- **Solution**: Commit the updated `.po` and `.mo` files

```powershell
# After running i18n.py locally
git add katrain/i18n/locales/*/LC_MESSAGES/katrain.po
git add katrain/i18n/locales/*/LC_MESSAGES/katrain.mo
git commit -m "chore(i18n): update translations for new keys"
```

---

## PR Review Checklist

Before merging a PR that adds new UI strings:

- [ ] All `i18n._("...")` calls use **key-style msgids** (not raw English)
- [ ] English `.po` file has `msgid` + `msgstr` for all new keys
- [ ] Japanese `.po` file has translations for all new keys
- [ ] `.mo` files regenerated (check git diff for both `.po` and `.mo`)
- [ ] No raw keys displayed in app (manual test: EN + JP)
- [ ] KV widgets have `lang_change_tracking: i18n._('')` if needed
- [ ] PowerShell commands tested on Windows 11
- [ ] CI passes (i18n.py may exit 1, commit the changes)
- [ ] No `msgstr ""` (empty) in `en/katrain.po`
- [ ] Naming follows convention: `namespace:category:key`

---

## FAQ

**Q: Why `jp` instead of `ja`?**
A: Historical convention in this repo. Do not change.

**Q: Can I use English phrases as msgid?**
A: No. English locale uses `.po`/`.mo` like other languages. Use key-style msgids.

**Q: Why does i18n.py add translations to all locales?**
A: It auto-fills missing msgids from `en` as fallback, so other locales don't break.

**Q: Do I need to translate to all 11 languages?**
A: No. Only `en` and `jp` are required. Others auto-fill from `en`.

**Q: What if I see "TODO" comments in .po files?**
A: These mark strings needing proper translation. Safe to ignore for now.

---

## Related Files

- **Runtime**: `katrain/core/lang.py` (Lang class, i18n object)
- **Extraction**: `i18n.py` (auto-fix + compile script)
- **Locales**: `katrain/i18n/locales/<lang>/LC_MESSAGES/katrain.{po,mo}`
- **Tests**: `tests/test_i18n.py` (validates .mo files are up-to-date)

---

## References

- gettext documentation: https://docs.python.org/3/library/gettext.html
- Kivy i18n: https://kivy.org/doc/stable/guide/lang.html#lang-localization
- polib (used by i18n.py): https://pypi.org/project/polib/

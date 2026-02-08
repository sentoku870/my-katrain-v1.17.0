
import re
import glob

def extract_keys(files):
    keys = set()
    pattern = re.compile(r"i18n\._\(['\"](.+?)['\"]\)")
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            found = pattern.findall(content)
            for k in found:
                keys.add(k)
                print(f"Found in {file_path}: {k}")
    return keys

files = [
    'katrain/core/reports/summary_report.py',
    'katrain/core/reports/karte/sections/diagnosis.py'
]

print("Extracting keys...")
keys = extract_keys(files)
print(f"\nTotal unique keys found: {len(keys)}")
with open('extracted_keys.txt', 'w', encoding='utf-8') as f:
    for k in sorted(keys):
        f.write(f"{k}\n")
print("Saved keys to extracted_keys.txt")


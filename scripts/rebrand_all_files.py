import os
import re

TARGET_DIR = "/Users/apple/Documents/Antigravity/untitled folder"

# File extensions to rebrand
EXTENSIONS = {".html", ".js", ".css", ".json", ".md", ".py"}

# Files or folders to skip
SKIP_DIRS = {".git", ".venv", "node_modules", "output", "temp", "cache", "brand_assets_old"}

# Replacements to make in ordered sequence
REPLACEMENTS = [
    # Exact HTML Brand markup
    ("DALAL STREET <span>ALPHA</span>", "THE BULL <span>PRINT</span>"),
    ("DALAL STREET <span>ALPHA </span>", "THE BULL <span>PRINT </span>"),
    ("DALAL STREET ALPHA", "THE BULL PRINT"),
    ("Dalal Street Alpha Logo", "The Bull Print Logo"),
    ("Dalal Street Alpha Desk", "The Bull Print Desk"),
    ("Dalal Street Alpha AI", "The Bull Print AI"),
    ("Dalal Street Alpha's", "The Bull Print's"),
    ("Dalal Street Alpha", "The Bull Print"),
    ("DALAL_STREET_ALPHA", "THE_BULL_PRINT"),
    ("dalal-street-alpha", "the-bull-print"),
    ("dalal_street_alpha", "the_bull_print"),
]

modified_files = []
total_replacements = 0

for root, dirs, files in os.walk(TARGET_DIR):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for file in files:
        ext = os.path.splitext(file)[1].lower()
        if ext in EXTENSIONS:
            filepath = os.path.join(root, file)
            # Avoid modifying this script itself
            if "rebrand_all_files.py" in filepath:
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                original_content = content
                file_count = 0
                for old_val, new_val in REPLACEMENTS:
                    count = content.count(old_val)
                    if count > 0:
                        content = content.replace(old_val, new_val)
                        file_count += count
                
                if content != original_content:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    modified_files.append((filepath, file_count))
                    total_replacements += file_count
            except Exception as e:
                print(f"Error processing {filepath}: {e}")

print(f"Total files updated: {len(modified_files)}")
print(f"Total occurrences replaced: {total_replacements}")
for path, count in modified_files:
    rel_path = os.path.relpath(path, TARGET_DIR)
    print(f"  - {rel_path}: {count} replacements")

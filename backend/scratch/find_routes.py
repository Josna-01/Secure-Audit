import os
import re

app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines, 1):
    if "@app." in line:
        print(f"Line {idx:4d}: {line.strip()}")

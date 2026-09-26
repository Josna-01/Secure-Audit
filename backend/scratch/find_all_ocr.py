import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for root, dirs, files in os.walk(backend_dir):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                for idx, line in enumerate(file, 1):
                    if "@app." in line or "ocr" in line.lower() and ("def " in line or "@" in line):
                        print(f"{os.path.relpath(path, backend_dir)}:{idx} -> {line.strip()}")

import os

req_path = os.path.join(os.path.dirname(__file__), "..", "..", "bns-backend", "requirements.txt")

# Try reading with utf-16le or utf-8
content = ""
for encoding in ["utf-16le", "utf-8", "utf-16"]:
    try:
        with open(req_path, "r", encoding=encoding) as f:
            content = f.read()
        print(f"Successfully read requirements.txt with {encoding}")
        break
    except Exception:
        pass

lines = content.splitlines()
new_lines = []
modified = False

for line in lines:
    stripped = line.strip()
    if stripped.startswith("numpy=="):
        new_line = "numpy>=2.0.0,<2.3.0"
        print(f"Replacing '{stripped}' -> '{new_line}'")
        new_lines.append(new_line)
        modified = True
    else:
        new_lines.append(line)

# Write back in standard utf-8
with open(req_path, "w", encoding="utf-8") as f:
    f.write("\n".join(new_lines) + "\n")

print(f"Updated requirements.txt saved in utf-8 format.")

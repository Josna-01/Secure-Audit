import os

req_path = os.path.join(os.path.dirname(__file__), "..", "..", "bns-backend", "requirements.txt")

with open(req_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []

for line in lines:
    stripped = line.strip()
    if "+" in stripped and not stripped.startswith("#") and "@" not in stripped:
        pkg_name = stripped.split(">=")[0].split("==")[0].split("<=")[0].strip()
        new_lines.append(f"{pkg_name}\n")
        print(f"Cleaned local version label from '{stripped}' -> '{pkg_name}'")
    else:
        new_lines.append(line)

with open(req_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Cleaned local version labels in bns-backend requirements.txt")

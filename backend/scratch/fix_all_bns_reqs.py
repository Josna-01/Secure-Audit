import os

req_path = os.path.join(os.path.dirname(__file__), "..", "..", "bns-backend", "requirements.txt")

with open(req_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
replacements = {
    "scikit-learn==1.8.0": "scikit-learn>=1.3.0,<1.8.0",
    "scipy==1.16.0": "scipy>=1.10.0,<1.15.0",
}

for line in lines:
    stripped = line.strip()
    replaced = False
    for old_pin, new_pin in replacements.items():
        if old_pin in stripped:
            print(f"Replacing '{stripped}' -> '{new_pin}'")
            new_lines.append(new_pin + "\n")
            replaced = True
            break
    if not replaced:
        new_lines.append(line)

with open(req_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Updated bns-backend requirements.txt")

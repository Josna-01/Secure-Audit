import os

req_path = os.path.join(os.path.dirname(__file__), "..", "..", "bns-backend", "requirements.txt")

with open(req_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []

for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        new_lines.append(line)
        continue

    # Keep URL packages (like en_core_web_sm@...) untouched
    if "@" in stripped:
        new_lines.append(line)
        continue

    # Convert strict == pins to >= or unpinned for Python 3.10 compatibility
    if "==" in stripped:
        pkg_name = stripped.split("==")[0].strip()
        # For packages known to have python 3.11+ version issues, loosen or remove pin
        if pkg_name.lower() in ["numpy", "scipy", "scikit-learn", "torch", "torchvision", "torchaudio", "spacy", "pydantic", "pydantic_core"]:
            new_lines.append(f"{pkg_name}\n")
            print(f"Unpinned {pkg_name} (was {stripped})")
        else:
            # Replace == with >= for general flexibility
            version = stripped.split("==")[1].strip()
            new_lines.append(f"{pkg_name}>={version}\n")
    else:
        new_lines.append(line)

with open(req_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Updated bns-backend requirements.txt for Python 3.10 compatibility.")

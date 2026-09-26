import os

app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

cutoff = None
for idx, line in enumerate(lines):
    if line.strip() == 'if __name__ == "__main__":':
        # Keep up to uvicorn.run
        cutoff = idx + 3
        break

if cutoff:
    truncated_lines = lines[:cutoff]
    with open(app_path, "w", encoding="utf-8") as f:
        f.writelines(truncated_lines)
    print(f"Successfully truncated app.py to {len(truncated_lines)} lines.")
else:
    print("Main block not found!")

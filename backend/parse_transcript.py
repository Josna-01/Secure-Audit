import json

transcript_path = r"C:\Users\amish\.gemini\antigravity-ide\brain\216481be-a41f-44fb-bd99-66a0c4ffe54d\.system_generated\logs\transcript.jsonl"

print("Parsing transcript...")
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line)
            content = data.get("content", "")
            if "alter_table.py" in content or "alter table" in content.lower():
                print(f"--- Step {data.get('step_index')} ({data.get('type')}) ---")
                print(content[:500])
                if "tool_calls" in data:
                    print("Tool Calls:", data["tool_calls"])
        except Exception as e:
            pass

from pathlib import Path
import re
import json
import demjson3

html_path = Path("content/ch11/olm_11.1-Adaptations-to-Aerobic-Training.html")
text = html_path.read_text(encoding="utf-8", errors="ignore")

match = re.search(r'(?:const|let|var)\s+assessmentBanks\s*=\s*\{', text)
if not match:
    print("Could not find assessmentBanks declaration")
    exit()

start_pos = match.end() - 1
brace_depth = 0
in_str = False
q_char = ''
escape = False
end_pos = -1

for i in range(start_pos, len(text)):
    c = text[i]
    if escape:
        escape = False
        continue
    if c == '\\':
        escape = True
        continue
    if in_str:
        if c == q_char:
            in_str = False
    else:
        if c in ('"', "'", '`'):
            in_str = True
            q_char = c
        elif c == '{':
            brace_depth += 1
        elif c == '}':
            brace_depth -= 1
            if brace_depth == 0:
                end_pos = i + 1
                break

raw_js = text[start_pos:end_pos]
print(f"Extracted block size: {len(raw_js)} characters.")

try:
    data = demjson3.decode(raw_js)
    total_q = sum(
        len(items)
        for part in data.values()
        if isinstance(part, dict)
        for items in part.values()
        if isinstance(items, list)
    )
    print(f"✓ demjson3 Success! Extracted {total_q} questions.")
    Path("content/ch11/11.1_quiz.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Saved to content/ch11/11.1_quiz.json")
except Exception as e:
    print(f"demjson3 error: {e}")
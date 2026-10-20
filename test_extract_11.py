import re
import json
from pathlib import Path

html_path = Path("content/ch11/olm_11.1-Adaptations-to-Aerobic-Training.html")
text = html_path.read_text(encoding="utf-8", errors="ignore")

# Find 'const assessmentBanks = {'
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
print(f"Extracted raw block of length: {len(raw_js)} characters.")

# Pure-Python JS -> JSON Converter
# 1. Quote unquoted keys: word followed by colon
s = re.sub(r'([{,]\s*)([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', raw_js)

# 2. Convert single-quoted string values to double-quoted string values safely
def fix_quotes(m):
    inner = m.group(1).replace('"', '\\"')
    return f'"{inner}"'
s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", fix_quotes, s)

# 3. Clean trailing commas
s = re.sub(r',\s*([\]}])', r'\1', s)

try:
    data = json.loads(s)
    total_q = sum(len(items) for part in data.values() if isinstance(part, dict) for items in part.values() if isinstance(items, list))
    print(f"✓ Success! Parsed JSON with {total_q} questions.")
    Path("content/ch11/11.1_quiz.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Saved to content/ch11/11.1_quiz.json")
except Exception as e:
    print(f"Parser error: {e}")
    # Print the line where it choked for immediate pinpointing
    lines = s.splitlines()
    m_err = re.search(r'line (\d+) column (\d+)', str(e))
    if m_err:
        line_num = int(m_err.group(1))
        print("Surrounding problematic text:")
        for idx in range(max(0, line_num - 3), min(len(lines), line_num + 3)):
            print(f"{idx+1}: {lines[idx]}")
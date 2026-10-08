import os
import re
import json
from pathlib import Path
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).parent.resolve()
CONTENT_DIR = REPO_ROOT / "content"

def extract_json_from_js(text_block, var_name):
    """
    Extracts a JS object variable (like assessmentBanks = { ... }) 
    from a script tag using balanced brace tracking.
    """
    pattern = rf'(?:var|let|const)?\s*{var_name}\s*=\s*(\{{)'
    match = re.search(pattern, text_block)
    if not match:
        return None
    
    start_pos = match.start(1)
    brace_depth = 0
    in_string = False
    quote_char = ''
    escape = False

    for idx in range(start_pos, len(text_block)):
        char = text_block[idx]
        
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
            
        if in_string:
            if char == quote_char:
                in_string = False
        else:
            if char in ('"', "'", '`'):
                in_string = True
                quote_char = char
            elif char == '{':
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    raw_obj = text_block[start_pos : idx + 1]
                    return clean_js_object_to_json(raw_obj)
    return None

def clean_js_object_to_json(js_str):
    """
    Converts loose JS object notation (unquoted keys, single quotes, trailing commas)
    into strict standard JSON.
    """
    # Replace single quoted strings with temporary double quote placeholders
    # or handle unquoted keys: { key: "val" } -> { "key": "val" }
    s = js_str

    # Quote unquoted property keys: word followed by colon
    s = re.sub(r'([{,]\s*)([a-zA-Z0-9_$]+)\s*:', r'\1"\2":', s)

    # Convert single-quoted string values to double quotes safely
    # (matches 'something' while preserving internal escapes)
    def repl_sq(m):
        inner = m.group(1).replace('"', '\\"')
        return f'"{inner}"'
    s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", repl_sq, s)

    # Remove trailing commas before closing braces/brackets
    s = re.sub(r',\s*([\]}])', r'\1', s)

    try:
        return json.loads(s)
    except Exception:
        # Fallback: lenient regex cleanup if strict parse fails
        try:
            import ast
            # If valid python literal
            py_dict = ast.literal_eval(js_str.replace('true', 'True').replace('false', 'False').replace('null', 'None'))
            return py_dict
        except Exception:
            return None

def process_html_file(file_path):
    print(f"\nProcessing: {file_path.name}")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        html_text = f.read()

    soup = BeautifulSoup(html_text, "html.parser")

    # Determine module ID (e.g. 10.1 or 11.2)
    mod_match = re.search(r'(?:OLM\s*-\s*|olm_)?(\d+\.\d+)', file_path.name)
    if not mod_match:
        print(f"  [!] Skipped: Could not determine module number from {file_path.name}")
        return
    mod_id = mod_match.group(1)
    ch_num = mod_id.split('.')[0]

    # 1. Extract Meta
    title_tag = soup.find("title")
    doc_title = title_tag.get_text().strip() if title_tag else file_path.stem
    # Remove OLM prefix if present
    clean_title = re.sub(r'^(?:OLM\s*-\s*|olm_)?\d+\.\d+[\s\-_:]*', '', doc_title).strip()

    meta = {
        "course": "PX – KINS 4403 Physiology of Exercise",
        "moduleTitle": f"{mod_id} {clean_title}",
        "chapter": ch_num,
        "section": mod_id
    }

    # 2. Extract Glossary
    glossary = []
    # Search for table rows in glossary table or pane-glossary
    gloss_pane = soup.find(id="pane-glossary") or soup.find(class_="glossary-table")
    if gloss_pane:
        rows = gloss_pane.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                term = cols[0].get_text().strip()
                definition = cols[1].get_text().strip()
                if term and definition and term.lower() != "term":
                    glossary.append({"term": term, "def": definition})

    # 3. Extract Reading Sections (pages)
    pages = []
    # Typical legacy layout: sections with id="sec-reading-p1", "page-p1", or concept-page-view
    concept_pages = soup.find_all("section", class_=re.compile(r'concept-page-view|concept-page', re.I))
    if not concept_pages:
        concept_pages = soup.find_all(id=re.compile(r'page-p\d+|sec-reading-p\d+'))

    # If specific sections found
    if concept_pages:
        for idx, sec in enumerate(concept_pages, start=1):
            pid = f"p{idx}"
            
            # Find page title from an internal heading
            h2 = sec.find(["h2", "h1"])
            ptitle = h2.get_text().strip() if h2 else f"Part {idx}"

            # Reading HTML: prefer #sec-reading-pX or inner contents
            reading_el = sec.find(id=re.compile(rf'sec-reading-{pid}|reading-content', re.I)) or sec
            reading_html = "".join([str(c) for c in reading_el.contents if getattr(c, 'name', None) not in ['script', 'style']]).strip()

            pages.append({
                "id": pid,
                "title": ptitle,
                "sampleCounts": { "mcq": 2, "ms": 2, "tf": 2, "cloze": 2, "sa": 1 },
                "readingHtml": reading_html,
                "activities": []
            })
    else:
        # Fallback if unsegmented: take main article or body
        main_body = soup.find("main") or soup.find("article") or soup.find("body")
        reading_html = "".join([str(c) for c in main_body.contents if getattr(c, 'name', None) not in ['script', 'style', 'header', 'footer']]).strip() if main_body else ""
        pages.append({
            "id": "p1",
            "title": clean_title or f"Module {mod_id}",
            "sampleCounts": { "mcq": 2, "ms": 2, "tf": 2, "cloze": 2, "sa": 1 },
            "readingHtml": reading_html,
            "activities": []
        })

    # Assemble content.json
    content_payload = {
        "meta": meta,
        "glossary": glossary,
        "pages": pages
    }

    # 4. Extract Assessment Bank from Scripts
    quiz_payload = {}
    scripts = soup.find_all("script")
    for scr in scripts:
        scr_content = scr.string or scr.get_text() or ""
        if "assessmentBanks" in scr_content or "assessmentBank" in scr_content:
            data = extract_json_from_js(scr_content, "assessmentBanks") or extract_json_from_js(scr_content, "assessmentBank")
            if data and isinstance(data, dict):
                quiz_payload = data
                break

    # Save Output Files directly in same chapter directory
    out_dir = file_path.parent
    content_file = out_dir / f"{mod_id}_content.json"
    quiz_file = out_dir / f"{mod_id}_quiz.json"

    with open(content_file, "w", encoding="utf-8") as f:
        json.dump(content_payload, f, indent=2, ensure_ascii=False)
    print(f"  [+] Created: {content_file.name} ({len(pages)} page(s), {len(glossary)} glossary terms)")

    with open(quiz_file, "w", encoding="utf-8") as f:
        json.dump(quiz_payload, f, indent=2, ensure_ascii=False)
    q_count = sum(len(items) for part in quiz_payload.values() if isinstance(part, dict) for items in part.values() if isinstance(items, list))
    print(f"  [+] Created: {quiz_file.name} ({q_count} assessment item(s) extracted)")

def main():
    target_chapters = ["ch10", "ch11"]
    for ch in target_chapters:
        ch_path = CONTENT_DIR / ch
        if not ch_path.exists():
            continue
        for html_file in ch_path.glob("*.html"):
            process_html_file(html_file)

    print("\n✓ Migration complete! Check content/ch10/ and content/ch11/.")

if __name__ == "__main__":
    main()
import os
import re
import json
from pathlib import Path
from bs4 import BeautifulSoup
import demjson3

REPO_ROOT = Path(__file__).parent.resolve()
CONTENT_DIR = REPO_ROOT / "content"

def extract_assessment_banks_raw(html_text):
    match = re.search(r'(?:const|let|var)\s+assessmentBanks\s*=\s*\{', html_text)
    if not match:
        return None
    start_pos = match.end() - 1
    brace_depth = 0
    in_str = False
    quote_char = ''
    escape = False

    for idx in range(start_pos, len(html_text)):
        ch = html_text[idx]
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if in_str:
            if ch == quote_char:
                in_str = False
        else:
            if ch in ('"', "'", '`'):
                in_str = True
                quote_char = ch
            elif ch == '{':
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    return html_text[start_pos : idx + 1]
    return None

def extract_clean_reading(sec_soup):
    """
    Extracts pure reading content, checking for <details id="sec-reading">,
    #sec-reading-pX, or isolating everything before the first question container.
    """
    # 1. Direct match: <details id="sec-reading"> or element with sec-reading
    reading_target = sec_soup.find(['details', 'div', 'section'], id=re.compile(r'sec-reading', re.I))
    
    # 2. If found, pull contents inside (strip out summary if it's a details tag)
    if reading_target:
        target_clone = BeautifulSoup(str(reading_target), "html.parser")
        sum_tag = target_clone.find('summary')
        if sum_tag:
            sum_tag.decompose()
        # Remove any stray buttons
        for btn in target_clone.find_all('button'):
            btn.decompose()
        return "".join(str(c) for c in target_clone.contents if getattr(c, 'name', None) not in ['script', 'style']).strip()

    # 3. Fallback: Take all children before the first assessment container (<details id="sec-mcq"> etc.)
    body_parts = []
    for child in sec_soup.children:
        if not getattr(child, 'name', None):
            continue
        cid = child.get('id', '')
        # Stop reading when hitting the assessment cards
        if re.search(r'sec-mcq|sec-ms|sec-tf|sec-cloze|sec-short|container-', cid, re.I):
            break
        if child.name not in ['script', 'style', 'header']:
            body_parts.append(str(child))
            
    return "".join(body_parts).strip()

def process_html_file(file_path):
    print(f"\nProcessing: {file_path.name}")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        html_text = f.read()

    soup = BeautifulSoup(html_text, "html.parser")

    mod_match = re.search(r'(?:OLM\s*-\s*|olm_)?(\d+\.\d+)', file_path.name)
    if not mod_match:
        print(f"  [!] Skipped: {file_path.name}")
        return
    mod_id = mod_match.group(1)
    ch_num = mod_id.split('.')[0]

    title_tag = soup.find("title")
    doc_title = title_tag.get_text().strip() if title_tag else file_path.stem
    clean_title = re.sub(r'^(?:OLM\s*-\s*|olm_)?\d+\.\d+[\s\-_:]*', '', doc_title).strip()

    meta = {
        "course": "PX – KINS 4403 Physiology of Exercise",
        "moduleTitle": f"{mod_id} {clean_title}",
        "chapter": ch_num,
        "section": mod_id
    }

    # Extract Glossary
    glossary = []
    gloss_pane = soup.find(id="pane-glossary") or soup.find(class_=re.compile(r'glossary', re.I))
    if gloss_pane:
        for row in gloss_pane.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 2:
                t = cols[0].get_text().strip()
                d = cols[1].get_text().strip()
                if t and d and t.lower() != "term":
                    glossary.append({"term": t, "def": d})

    # Extract Concept Pages using class="concept-page-view"
    pages = []
    concept_sections = soup.find_all(['section', 'div'], class_=re.compile(r'concept-page-view|concept-page', re.I))
    
    if not concept_sections:
        # Fallback to checking IDs with page-
        concept_sections = soup.find_all(['section', 'div'], id=re.compile(r'^page-', re.I))

    if concept_sections:
        for idx, sec in enumerate(concept_sections, start=1):
            pid = f"p{idx}"
            # Extract clean heading
            h2 = sec.find(['h2', 'h1', 'h3'])
            ptitle = h2.get_text().strip() if h2 else f"Part {idx}"
            # Strip out "Concept X:" prefixes if present
            clean_ptitle = re.sub(r'^(?:Part|Concept|Topic)\s*\d*[:\s-]*', '', ptitle).strip()

            reading_html = extract_clean_reading(sec)

            pages.append({
                "id": pid,
                "title": clean_ptitle or f"Part {idx}",
                "sampleCounts": { "mcq": 2, "ms": 2, "tf": 2, "cloze": 2, "sa": 1 },
                "readingHtml": reading_html,
                "activities": []
            })
    else:
        # Single page structure fallback
        reading_html = extract_clean_reading(soup)
        pages.append({
            "id": "p1",
            "title": clean_title or f"Module {mod_id}",
            "sampleCounts": { "mcq": 2, "ms": 2, "tf": 2, "cloze": 2, "sa": 1 },
            "readingHtml": reading_html,
            "activities": []
        })

    content_payload = {
        "meta": meta,
        "glossary": glossary,
        "pages": pages
    }

    # Extract Assessment Bank
    quiz_payload = {}
    raw_block = extract_assessment_banks_raw(html_text)
    if raw_block:
        try:
            raw_data = demjson3.decode(raw_block)
            # Normalize keys to p1, p2, p3 if they used named keys
            keys = list(raw_data.keys())
            for idx, k in enumerate(keys):
                norm_key = f"p{idx+1}"
                quiz_payload[norm_key] = raw_data[k]
                # Keep original key as well for compatibility
                quiz_payload[k] = raw_data[k]
        except Exception as e:
            print(f"  [!] demjson3 decode error on {file_path.name}: {e}")

    out_dir = file_path.parent
    content_file = out_dir / f"{mod_id}_content.json"
    quiz_file = out_dir / f"{mod_id}_quiz.json"

    with open(content_file, "w", encoding="utf-8") as f:
        json.dump(content_payload, f, indent=2, ensure_ascii=False)

    with open(quiz_file, "w", encoding="utf-8") as f:
        json.dump(quiz_payload, f, indent=2, ensure_ascii=False)

    item_count = 0
    if isinstance(quiz_payload, dict):
        for part in quiz_payload.values():
            if isinstance(part, dict):
                for q_list in part.values():
                    if isinstance(q_list, list):
                        item_count += len(q_list)

    print(f"  [+] Saved {content_file.name} (Pages: {len(pages)}, Glossary: {len(glossary)})")
    print(f"  [+] Saved {quiz_file.name} (Pool: {item_count} items indexed)")

def main():
    for ch in ["ch10", "ch11"]:
        ch_path = CONTENT_DIR / ch
        if not ch_path.exists():
            continue
        for html_file in sorted(ch_path.glob("*.html")):
            if html_file.name in ["index.html", "viewer.html"]:
                continue
            process_html_file(html_file)

    print("\n✓ Migration complete! All pages and question pools cleanly parsed.")

if __name__ == "__main__":
    main()
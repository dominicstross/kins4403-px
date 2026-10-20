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

def clean_reading_soup(soup_section):
    tags = ['div', 'section', 'h2', 'h3', 'h4', 'button', 'p']
    for el in soup_section.find_all(tags):
        el_text = el.get_text() if el.string or el.contents else ''
        el_id = el.get('id', '')
        el_cls = " ".join(el.get('class', []))

        if re.search(r'Formative Assessment|Interactive Knowledge Check', el_text, re.I):
            el.decompose()
            continue

        combined_attr = f"{el_id} {el_cls}"
        if re.search(r'container-p\d+|reset-btn|activity-section', combined_attr, re.I):
            el.decompose()
            continue

        if el.name == 'button' and re.search(r'reset|check|submit', el_text, re.I):
            el.decompose()
            continue

    child_nodes = [c for c in soup_section.contents if getattr(c, 'name', None) not in ['script', 'style']]
    return "".join(str(c) for c in child_nodes).strip()

def process_html_file(file_path):
    print(f"\nProcessing: {file_path.name}")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        html_text = f.read()

    soup = BeautifulSoup(html_text, "html.parser")

    mod_match = re.search(r'(?:OLM\s*-\s*|olm_)?(\d+\.\d+)', file_path.name)
    if not mod_match:
        print(f"  [!] Skipped: Could not determine module number from {file_path.name}")
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

    # Extract Clean Reading Pages
    pages = []
    concept_pages = soup.find_all("section", class_=re.compile(r'concept-page-view|concept-page', re.I))
    if not concept_pages:
        concept_pages = soup.find_all(id=re.compile(r'page-p\d+|sec-reading-p\d+'))

    if concept_pages:
        for idx, sec in enumerate(concept_pages, start=1):
            pid = f"p{idx}"
            h2 = sec.find(["h2", "h1"])
            ptitle = h2.get_text().strip() if h2 else f"Part {idx}"
            
            p_pattern = re.compile(rf'sec-reading-{pid}|reading-content', re.I)
            reading_el = sec.find(id=p_pattern)
            if not reading_el:
                reading_el = sec
            
            clean_html = clean_reading_soup(reading_el)

            pages.append({
                "id": pid,
                "title": ptitle,
                "sampleCounts": { "mcq": 2, "ms": 2, "tf": 2, "cloze": 2, "sa": 1 },
                "readingHtml": clean_html,
                "activities": []
            })
    else:
        main_body = soup.find("main") or soup.find("article") or soup.find("body")
        clean_html = clean_reading_soup(main_body) if main_body else ""
        pages.append({
            "id": "p1",
            "title": clean_title or f"Module {mod_id}",
            "sampleCounts": { "mcq": 2, "ms": 2, "tf": 2, "cloze": 2, "sa": 1 },
            "readingHtml": clean_html,
            "activities": []
        })

    content_payload = {
        "meta": meta,
        "glossary": glossary,
        "pages": pages
    }

    # Extract Question Bank with demjson3
    quiz_payload = {}
    raw_block = extract_assessment_banks_raw(html_text)
    if raw_block:
        try:
            quiz_payload = demjson3.decode(raw_block)
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

    print(f"  [+] Saved {content_file.name} ({len(glossary)} glossary terms)")
    print(f"  [+] Saved {quiz_file.name} ({item_count} questions extracted)")

def main():
    for ch in ["ch10", "ch11"]:
        ch_path = CONTENT_DIR / ch
        if not ch_path.exists():
            continue
        for html_file in sorted(ch_path.glob("*.html")):
            if html_file.name in ["index.html", "viewer.html"]:
                continue
            process_html_file(html_file)

    print("\n✓ Batch migration complete!")

if __name__ == "__main__":
    main()
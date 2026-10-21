with open("index.html", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Preserve <head> and the complete styling exactly as designed
head_end = text.find("</head>")
if head_end == -1:
    print("Could not find </head>")
    exit(1)

head_section = text[:head_end + 7]

# Clean, dynamic body that reads content/manifest.json
dynamic_body = """
<body>
  <header class="top-bar">
    <div class="top-bar-inner">
      <div id="courseInst" class="inst-pill">Southeastern University</div>
      <h1 id="courseTitle">Exercise Science Learning Portal</h1>
      <p id="courseDesc">Interactive online modules, laboratory simulations, and conceptual mastery.</p>
    </div>
  </header>

  <main class="container" id="unitsContainer">
    <div style="text-align: center; padding: 48px; color: var(--slate-500); font-weight: 500;">
      Loading course curriculum...
    </div>
  </main>

  <script>
    async function loadCoursePortal() {
      const container = document.getElementById("unitsContainer");
      try {
        const res = await fetch("content/manifest.json");
        if (!res.ok) throw new Error("Status " + res.status);
        const data = await res.json();

        // Update header metadata
        if (data.institution) document.getElementById("courseInst").textContent = data.institution;
        if (data.courseTitle) document.getElementById("courseTitle").textContent = data.courseTitle;
        if (data.description) document.getElementById("courseDesc").textContent = data.description;
        if (data.courseCode) document.title = `${data.courseCode} - Course Portal`;

        if (!data.units || !data.units.length) {
          container.innerHTML = '<div style="padding:24px; text-align:center;">No course units found in manifest.</div>';
          return;
        }

        container.innerHTML = "";

        data.units.forEach((unit, uIdx) => {
          const unitSec = document.createElement("section");
          unitSec.className = "unit-section";

          unitSec.innerHTML = `
            <div class="unit-header">
              <h2 class="unit-title">${unit.unitTitle || ("Unit " + (uIdx + 1))}</h2>
              ${unit.unitTag ? `<span class="unit-tag">${unit.unitTag}</span>` : ""}
            </div>
            <div class="unit-chapters" id="unit-chapters-${uIdx}"></div>
          `;

          const chapContainer = unitSec.querySelector(`#unit-chapters-${uIdx}`);

          (unit.chapters || []).forEach((ch, chIdx) => {
            const details = document.createElement("details");
            details.className = "chapter-accordion";
            // Keep first chapter open by default
            if (uIdx === 0 && chIdx === 0) details.open = true;

            let modLinksHtml = "";
            (ch.modules || []).forEach(m => {
              const href = m.href || `viewer.html?ch=${ch.num}&mod=${m.id}`;
              modLinksHtml += `
                <a href="${href}" class="module-card">
                  <div class="module-card-body">
                    <span class="module-id-badge">${m.id || "Mod"}</span>
                    <span class="module-title-text">${m.title || "Interactive Lesson"}</span>
                  </div>
                  <span class="module-arrow">&rarr;</span>
                </a>
              `;
            });

            details.innerHTML = `
              <summary>
                <div class="summary-left">
                  <span class="chapter-chevron">&#9656;</span>
                  <span class="chapter-name">${ch.title || ("Chapter " + ch.num)}</span>
                </div>
                <span class="module-count">${(ch.modules || []).length} Modules</span>
              </summary>
              <div class="chapter-content">
                <div class="module-list">
                  ${modLinksHtml || '<div style="padding:12px; color:var(--slate-400); font-size:0.9rem;">Modules in development.</div>'}
                </div>
              </div>
            `;

            chapContainer.appendChild(details);
          });

          container.appendChild(unitSec);
        });

      } catch (err) {
        console.error("Portal render error:", err);
        container.innerHTML = `
          <div style="background:#fee2e2; border:1px solid #f87171; padding:24px; border-radius:8px; color:#991b1b; margin-top:20px; text-align:center;">
            <h3>Failed to load course modules</h3>
            <p style="margin-top:8px; font-size:0.9rem;">Could not load <code>content/manifest.json</code>. Ensure the local server is running.</p>
          </div>
        `;
      }
    }

    document.addEventListener("DOMContentLoaded", loadCoursePortal);
  </script>
</body>
</html>
"""

# Append any minor supplemental card/accordion styles needed if missing
custom_inline_css = """
<style>
  .module-list { display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; }
  .module-card {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 16px; background: #fff; border: 1px solid var(--slate-200);
    border-radius: 8px; text-decoration: none; color: var(--slate-800);
    transition: all 0.15s ease;
  }
  .module-card:hover {
    border-color: var(--accent); background: var(--accent-bg);
    transform: translateX(4px);
  }
  .module-card-body { display: flex; align-items: center; gap: 12px; }
  .module-id-badge {
    background: var(--slate-100); color: var(--slate-700);
    font-size: 0.75rem; font-weight: 700; padding: 4px 8px;
    border-radius: 6px; font-family: 'JetBrains Mono', monospace;
  }
  .module-card:hover .module-id-badge { background: #dbeafe; color: var(--accent); }
  .module-title-text { font-weight: 600; font-size: 0.95rem; }
  .module-arrow { color: var(--slate-400); font-weight: bold; }
  .module-card:hover .module-arrow { color: var(--accent); }
  summary {
    cursor: pointer; user-select: none; padding: 16px 20px;
    display: flex; align-items: center; justify-content: space-between;
    font-weight: 700; color: var(--slate-800); list-style: none;
  }
  summary::-webkit-details-marker { display: none; }
  .summary-left { display: flex; align-items: center; gap: 10px; }
  .module-count { font-size: 0.8rem; color: var(--slate-500); background: var(--slate-100); padding: 3px 8px; border-radius: 9999px; }
  details[open] summary .chapter-chevron { transform: rotate(90deg); }
  .chapter-chevron { display: inline-block; transition: transform 0.2s ease; font-size: 0.85rem; color: var(--slate-500); }
</style>
"""

final_html = head_section[:-7] + custom_inline_css + "</head>" + dynamic_body

with open("index.html", "w", encoding="utf-8") as f:
    f.write(final_html)

print("SUCCESS: index.html converted to dynamic manifest-driven engine!")

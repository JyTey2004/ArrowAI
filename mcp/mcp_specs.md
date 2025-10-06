# AI Consultant Sub-Agents and Tools

## 1. CodeSubAgent (Data Analyst)
- **Role**: Ingest datasets, run transformations, statistical analysis, create plots.
- **Tools**: pandas / polars, statsmodels, sklearn, matplotlib/plotly.
- **Outputs**:
  - `artifacts.json` (tables, metrics, metadata)
  - `figures/*.png`

---

## 2. ResearchAgent
- **Role**: Perform iterative web research and summarize findings.
- **Tools**: Web search, page fetcher, PDF downloader/OCR.
- **Outputs**:
  - `sources.json` (links, metadata, quotes)
  - `notes.md` (annotated research notes)

---

## 3. NarrativeAgent (Writer)
- **Role**: Turn research + analysis into a professional storyline.
- **Tools**: Style guide, summarizer, outline → prose expander.
- **Outputs**:
  - `narrative.md` (main storyline)
  - `exec_summary.md` (1–2 page executive brief)

---

## 4. SlideCraftAgent (Presentation Builder)
- **Role**: Transform narrative + figures into polished slides.
- **Tools**: Deck generator (PPTX/Google Slides), chart inserter, brand/theme assets.
- **Outputs**:
  - `deck.pptx`
  - `speaker_notes.md`

---

## 5. Optional Supporting Agents
- **FactCheckAgent**
  - Verifies numbers and claims against sources.
  - **Output**: `claim_map.json` (claim → source mapping)

- **QA/ComplianceAgent**
  - Checks formatting, consistency, branding, disclaimers.
  - **Output**: `qa_report.md`

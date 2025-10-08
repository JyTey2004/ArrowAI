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

## 2b. ArtifactService
- **Role**: Retrieve artifacts stored on S3 and expose text previews to other agents.
- **Tooling**:
  - `fetch_artifact_text` MCP tool – accepts an `s3://` URI and returns decoded text or a presigned download URL for binary files.
  - `understand_file` MCP tool – appends artifact insights to `ARTIFACTS.md`, falling back to the coding agent for large files.
  - `ping` MCP tool – liveness check.
- **Notes**:
  - Defaults to the `MCP_BUCKET` bucket and truncates responses at ~32 KB (configurable).
  - Binary formats return metadata plus a presigned link instead of raw bytes.

---

## 3. NarrativeAgent (Writer)
- **Role**: Turn research + analysis into a professional storyline.
- **Tooling**:
  - `compose_narrative` MCP tool – ingests artifacts and returns narrative + executive summary markdown (optionally uploads to S3).
  - `ping` MCP tool – liveness check.
- **Outputs**:
  - `narrative.md` (main storyline)
  - `executive_summary.md` (1–2 page executive brief)
  - `talking_points.md` (optional quick-reference bullets)

---

## 4. PresentationAgent (Presentation Builder)
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

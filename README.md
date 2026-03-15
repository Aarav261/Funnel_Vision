# Funnel Vision

Funnel Vision is an AI-powered landing page teardown tool.

It captures your page, analyzes conversion elements with Claude using a FLOW framework, overlays visual bounding-box diagnostics, generates a PDF teardown report, and provides an in-app follow-up chatbot for implementation questions.

## What It Does

1. Scrapes a landing page and captures a full-page screenshot.
2. Extracts text and button bounding boxes from the DOM.
3. Sends visual + structural context to Claude for conversion analysis.
4. Produces a visual PDF report with color-coded overlays.
5. Shows grouped issue insights in Streamlit.
6. Enables a contextual AI chat assistant after analysis.

## FLOW Framework Used

The analysis categorizes issues into:

1. Friction
2. Legitimacy
3. Offer Clarity
4. Willingness to Buy

## Tech Stack

1. UI: Streamlit
2. Browser automation and capture: Playwright + AgentQL
3. LLM analysis and chat: Anthropic Claude via LangChain
4. Report rendering: Pillow + FPDF2
5. Packaging and dependency management: uv / pip

## Project Structure

1. [app.py](app.py): Streamlit app entry point, full pipeline orchestration, and post-analysis chat UI.
2. [src/scraper.py](src/scraper.py): Browser automation, screenshot capture, and DOM box extraction.
3. [src/analyze_local.py](src/analyze_local.py): Claude FLOW analysis and JSON output creation.
4. [src/pdf_generator.py](src/pdf_generator.py): Builds report inputs from scraped + analyzed artifacts.
5. [src/report_generator.py](src/report_generator.py): Draws overlays/legend and writes final PDF.
6. [src/main.py](src/main.py): Script-based pipeline entry point (non-UI).
7. [src/delete_screenshots.py](src/delete_screenshots.py): Cleanup helper for screenshot artifacts.

## Prerequisites

1. Python 3.13+
2. One of:
   1. uv (recommended)
   2. pip + virtual environment
3. API keys:
   1. ANTHROPIC_API_KEY (required for analysis and assistant chat)
   2. AGENTQL_API_KEY (recommended/required for AgentQL queries, depending on your account/setup)

## Environment Variables

Create a .env file in the project root:

```env
ANTHROPIC_API_KEY=your_anthropic_key
AGENTQL_API_KEY=your_agentql_key
```

Notes:

1. If ANTHROPIC_API_KEY is missing, analysis and chat cannot run.
2. If AgentQL is not authenticated/configured, scraping query steps may fail.

## Installation

### Option A: uv (recommended)

```bash
uv sync
```

### Option B: pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Run the App (Primary Workflow)

```bash
uv run streamlit run app.py
```

Then open the local URL shown by Streamlit (usually http://localhost:8501).

### In-App Flow

1. Enter a landing page URL.
2. Click Analyze Funnel.
3. Wait for scrape + Claude analysis + PDF generation.
4. Review:
   1. Visual teardown preview (left)
   2. Structured Claude FLOW issues (right)
   3. AI CRO Assistant chat (below report section)
5. Download funnel_teardown_report.pdf.

## Script Workflow (No Streamlit)

You can also run the pipeline from the terminal:

```bash
uv run python src/main.py "https://example.com"
```

If no URL is provided, [src/main.py](src/main.py) uses its internal default URL.

## Output Artifacts

Generated files in project root:

1. scrape_results.json: raw scrape payload, text/button boxes, screenshot paths.
2. flow_analysis.json: Claude output with structured FLOW issues.
3. teardown_report.pdf: final visual report with overlays and legend.

Intermediate folder:

1. page_screenshots/: captured screenshots used during processing.

Cleanup:

1. [src/delete_screenshots.py](src/delete_screenshots.py) clears screenshot files after successful runs.

## Bounding Box Visualization

The PDF overlay currently uses:

1. Scored issue boxes (selected by Claude): heatmap colors by score.
2. Non-selected boxes: green highlight.
3. A legend in the top-right area of each report image to explain colors.

## Assistant Chat Behavior

The Streamlit chatbot:

1. Is available after a successful analysis.
2. Uses the current flow_analysis.json context plus recent chat turns.
3. Resets chat history when a new analysis result is generated.

## Common Commands

Run app:

```bash
uv run streamlit run app.py
```

Run script pipeline:

```bash
uv run python src/main.py "https://example.com"
```

Remove screenshots manually:

```bash
uv run python src/delete_screenshots.py
```

## Troubleshooting

### 1) Missing API key errors

Symptom:

1. Analysis fails, or chat says ANTHROPIC_API_KEY is missing.

Fix:

1. Add ANTHROPIC_API_KEY to .env.
2. Restart Streamlit.

### 2) Browser / Playwright issues

Symptom:

1. Scraper fails to launch Chromium.

Fix:

1. Run: python -m playwright install chromium
2. On Linux/containers, install system libraries listed in [packages.txt](packages.txt).

### 3) AgentQL query failures

Symptom:

1. Scrape step fails around AgentQL calls.

Fix:

1. Ensure AGENTQL_API_KEY is configured.
2. Re-run after validating network access.

### 4) No report generated

Symptom:

1. teardown_report.pdf not created.

Fix:

1. Verify page_screenshots contains at least one PNG.
2. Confirm flow_analysis.json exists and contains issues array.

## Security and Privacy Notes

1. Page screenshots and extracted on-page text are sent to external AI services during analysis.
2. Do not run this tool against sensitive/private pages unless you are authorized.
3. Review vendor data-handling policies for compliance requirements.

## Development Notes

1. requirements.txt is generated from pyproject.toml.
2. The Streamlit app currently auto-attempts Playwright Chromium install at startup.
3. tests directory currently has no active test suite.

## License

No license file is currently present in this repository.

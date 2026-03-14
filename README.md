# Funnel Vision

Funnel Vision is a tool to scrape, analyze, and generate AI-driven teardown reports for websites. It uses an automated pipeline powered by headless browsers (Playwright + AgentQL), Anthropic's Claude, and a custom PDF generator to identify conversion friction, legitimacy issues, offer clarity, and the willingness to buy.

## 🚀 Streamlit Inteface

The project has been refactored to include a **Streamlit Web UI**.

### Setup and Running the UI

1. Make sure your dependencies are installed (including Streamlit):
   ```bash
   uv sync
   ```

2. Run the Streamlit application:
   ```bash
   uv run streamlit run app.py
   ```

3. Open your browser to the local URL (usually `http://localhost:8501`), enter a target webpage URL, and click **Analyze Funnel**.

The application will handle the entire sequence (Scraping -> LLM Analysis -> PDF Generation) directly in the UI and present you with a native Download button when it's done!

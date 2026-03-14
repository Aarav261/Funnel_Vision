import sys
import os
import asyncio
import subprocess
from dotenv import load_dotenv

# Safely install playwright browsers on Streamlit Cloud
try:
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
except Exception as e:
    print("Playwright install suppressed or failed", e)

import json
import tempfile
import threading
import base64
from pathlib import Path
import streamlit as st
from streamlit_pdf_viewer import pdf_viewer
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# Add src to the path
sys.path.append(str(Path(__file__).parent / "src"))

# Now we can import from src directly as if we are in it
from pdf_generator import main as generate_report
from scraper import run_full_scrape
from analyze_local import main as run_analysis
from delete_screenshots import delete_screenshots

st.set_page_config(page_title="Funnel Vision", layout="wide")
load_dotenv()

try:
    st.image("logo.png", width=300)
except:
    pass
st.write("Stop guessing, start selling. Your AI Conversion Strategist for High-Ticket Sales Funnels")

url = st.text_input("Enter Landing Page URL", placeholder="https://www.example.com")

async def run_pipeline(target_url: str):
    # 1. Scrape the website
    st.info(f"Scraping {target_url}... (This may take a minute)")
    payload = await run_full_scrape(target_url)
    
    output_path = Path("scrape_results.json")
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    
    # 2. Analyze the components using Claude
    st.info("Running AI analysis with Claude (FLOW Framework)...")
    await run_analysis()

    # 3. Generate the PDF
    st.info("Generating final PDF report...")
    generate_report()

    # 4. Clean up screenshots
    delete_screenshots()


def ask_flow_assistant(question: str, flow_data: dict, page_url: str, history: list[dict[str, str]]) -> str:
    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=1200)
    system_prompt = (
        "You are Funnel Vision Assistant, an expert conversion strategist. "
        "Answer questions about improving the user's landing page using the provided FLOW analysis context. "
        "Be practical, concise, and specific. Prioritize actionable copy and layout suggestions. "
        "If the user asks something not covered by context, say what is missing and give best-practice guidance."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Landing page URL: {page_url}\n\n"
                f"FLOW analysis JSON context:\n{json.dumps(flow_data, indent=2)}"
            )
        ),
    ]

    # Keep only recent turns for context window efficiency.
    for turn in history[-8:]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=question))
    result = llm.invoke(messages)
    return str(result.content)


def render_analysis_results(target_url: str) -> None:
    pdf_path = Path("teardown_report.pdf")
    flow_path = Path("flow_analysis.json")

    if not pdf_path.exists():
        st.error("Failed to generate PDF.")
        return

    st.success("✅ Analysis Complete!")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chat_context_key" not in st.session_state:
        st.session_state.chat_context_key = None

    flow_data: dict | None = None

    # Create two columns: Left for PDF, Right for Analysis
    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### Visual Teardown Preview")
        with open(pdf_path, "rb") as pdf_file:
            PDFbyte = pdf_file.read()

        st.download_button(
            label="Download Teardown PDF",
            data=PDFbyte,
            file_name="funnel_teardown_report.pdf",
            mime='application/octet-stream'
        )
        pdf_viewer(pdf_path, width=700, height=800)

    with col2:
        st.markdown("### Claude FLOW Analysis")
        if flow_path.exists():
            with open(flow_path, "r", encoding="utf-8") as f:
                flow_data = json.load(f)

            # Reset chat when a new analysis result is generated.
            current_context_key = json.dumps(flow_data, sort_keys=True)
            if st.session_state.chat_context_key != current_context_key:
                st.session_state.chat_context_key = current_context_key
                st.session_state.chat_history = []

            issues = flow_data.get("issues", [])
            if issues:
                # Group issues by category
                grouped_issues = {}
                for issue in issues:
                    cat = issue.get("category", "General")
                    if cat not in grouped_issues:
                        grouped_issues[cat] = []
                    grouped_issues[cat].append(issue)

                # Render neatly in Streamlit
                for cat, items in grouped_issues.items():
                    with st.expander(f"**{cat}** ({len(items)} issues)", expanded=True):
                        for item in items:
                            score = item.get("score", "-")
                            score_color = "red" if isinstance(score, int) and score < 5 else "green"

                            st.markdown(f"**Element:** {item.get('element_name')} *(Score: :{score_color}[{score}/10])*")
                            st.markdown(f"**Fix:** {item.get('suggested_text_fix', '')}")
                            st.divider()
            else:
                st.info("No major issues found by the AI!")
        else:
            st.warning("Could not locate flow analysis data.")

    if flow_data is not None:
        st.markdown("### Ask the AI CRO Assistant")
        st.caption("Ask follow-up questions about improving this exact landing page using Claude's analysis context.")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_question = st.chat_input("Ask how to improve your page based on this analysis")
        if user_question:
            st.session_state.chat_history.append({"role": "user", "content": user_question})
            with st.chat_message("user"):
                st.markdown(user_question)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        if not os.getenv("ANTHROPIC_API_KEY"):
                            assistant_reply = "ANTHROPIC_API_KEY is missing, so I cannot answer yet. Add it to your environment to use chat."
                        else:
                            assistant_reply = ask_flow_assistant(
                                user_question,
                                flow_data,
                                target_url,
                                st.session_state.chat_history[:-1],
                            )
                        st.markdown(assistant_reply)
                    except Exception as chat_error:
                        assistant_reply = f"Chat assistant error: {chat_error}"
                        st.error(assistant_reply)

            st.session_state.chat_history.append({"role": "assistant", "content": assistant_reply})


if "analysis_ready" not in st.session_state:
    st.session_state.analysis_ready = False
if "analysis_target" not in st.session_state:
    st.session_state.analysis_target = ""


if st.button("Analyze Funnel"):
    if not url:
        st.warning("Please enter a valid URL.")
    else:
        target = url.strip()
        if not target.startswith("http://") and not target.startswith("https://"):
            target = f"https://{target}"
            
        with st.spinner("Processing..."):
            try:
                asyncio.run(run_pipeline(target))
                st.session_state.analysis_ready = True
                st.session_state.analysis_target = target
            except Exception as e:
                st.error(f"An error occurred: {e}")
                delete_screenshots() # cleanup on error


if st.session_state.analysis_ready:
    render_analysis_results(st.session_state.analysis_target)

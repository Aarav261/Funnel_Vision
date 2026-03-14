import sys
import os
import asyncio
import subprocess

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

# Add src to the path
sys.path.append(str(Path(__file__).parent / "src"))

# Now we can import from src directly as if we are in it
from pdf_generator import main as generate_report
from scraper import scrape_page
from scraper import collect_text_and_button_boxes
from analyze_local import main as run_analysis
from delete_screenshots import delete_screenshots

st.set_page_config(page_title="Funnel Vision", layout="wide")

try:
    st.image("logo.png", width=300)
except:
    pass
st.title("Funnel Vision Teardown 🔍")
st.write("Generate an AI-driven, highly optimized teardown of any landing page.")

url = st.text_input("Enter Landing Page URL", placeholder="https://www.example.com")

async def run_pipeline(target_url: str):
    # 1. Scrape the website
    st.info(f"Scraping {target_url}... (This may take a minute)")
    scrape_result = await scrape_page(target_url)
    box_result = await collect_text_and_button_boxes(target_url)
    payload = {
        "scrape_page": scrape_result,
        "collect_text_and_button_boxes": box_result,
    }
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
                
                pdf_path = Path("teardown_report.pdf")
                flow_path = Path("flow_analysis.json")

                if pdf_path.exists():
                    st.success("✅ Analysis Complete!")
                    
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

                else:
                    st.error("Failed to generate PDF.")
            except Exception as e:
                st.error(f"An error occurred: {e}")
                delete_screenshots() # cleanup on error

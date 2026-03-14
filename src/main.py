import sys
import asyncio
import json
from pathlib import Path

from pdf_generator import main as generate_report
from scraper import scrape_page
from scraper import collect_text_and_button_boxes
from analyze_local import main as run_analysis
from delete_screenshots import delete_screenshots

async def run_scraper(url: str) -> None:
    scrape_result = await scrape_page(url)
    box_result = await collect_text_and_button_boxes(url)
    payload = {
        "scrape_page": scrape_result,
        "collect_text_and_button_boxes": box_result,
    }
    output_path = Path("scrape_results.json")
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved scrape results to {output_path}")

async def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://www.paidtobringpeace.com/blueprints"

    # 1. Scrape the website
    print(f"Scraping {url}...")
    await run_scraper(url)

    # 2. Analyze the components using Claude
    print("Running AI analysis...")
    await run_analysis()

    # 3. Generate the PDF
    print("Generating PDF...")
    generate_report()

    # 4. Clean up screenshots
    print("Cleaning up temporary screenshots...")
    delete_screenshots()

if __name__ == "__main__":
    asyncio.run(main())

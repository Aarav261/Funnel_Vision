
import asyncio
import json
from pathlib import Path

from scraper import scrape_page
from scraper import collect_text_and_button_boxes



from report_generator import generate_teardown_report


def main() -> None:
    flow_data = json.loads(Path("flow_analysis.json").read_text(encoding="utf-8"))
    issues = flow_data.get("issues", [])

    fallback_images = sorted(Path("page_screenshots").glob("*.png"))
    image_paths = [str(path) for path in fallback_images]
    if not image_paths:
        raise FileNotFoundError("No screenshot found. Ensure page_screenshots has images.")

    bounding_boxes = []
    flow_analysis = {
        "Friction": "",
        "Legitimacy": "",
        "Offer Clarity": "",
        "Willingness to Buy": ""
    }

    for issue in issues:
        bbox = issue.get("bounding_box")
        if bbox:
            bbox_copy = bbox.copy()
            bbox_copy["score"] = issue.get("score")
            bounding_boxes.append(bbox_copy)
        
        cat = issue.get("category")
        if cat in flow_analysis:
            elem = issue.get("element_name", "Element").replace("→", "->").encode("latin-1", "ignore").decode("latin-1")
            score = issue.get("score", "-")
            fix = issue.get("suggested_text_fix", "").replace("→", "->").encode("latin-1", "ignore").decode("latin-1")
            flow_analysis[cat] += f"- {elem} (Score: {score}/10): {fix}\n"

    report_path = generate_teardown_report(image_paths, bounding_boxes, flow_analysis)
    print(f"Teardown report generated at: {report_path}")


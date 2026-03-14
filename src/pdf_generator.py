
import asyncio
import json
from pathlib import Path

from report_generator import generate_teardown_report


def main() -> None:
    flow_data = json.loads(Path("flow_analysis.json").read_text(encoding="utf-8"))
    issues = flow_data.get("issues", [])
    scrape_data = {}
    scrape_path = Path("scrape_results.json")
    if scrape_path.exists():
        scrape_data = json.loads(scrape_path.read_text(encoding="utf-8"))

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

    # Start with all scraped text/button boxes so the full page can be highlighted.
    all_box_index: dict[tuple[int, int, int, int], int] = {}
    box_source = scrape_data.get("collect_text_and_button_boxes", {})

    def add_box(box: dict) -> None:
        x = box.get("x")
        y = box.get("y")
        width = box.get("width")
        height = box.get("height")
        if x is None or y is None or width is None or height is None:
            return
        try:
            key = (
                int(round(float(x))),
                int(round(float(y))),
                int(round(float(width))),
                int(round(float(height))),
            )
        except (ValueError, TypeError):
            return
        if key in all_box_index:
            return
        all_box_index[key] = len(bounding_boxes)
        bounding_boxes.append(
            {
                "x": float(x),
                "y": float(y),
                "width": float(width),
                "height": float(height),
            }
        )

    if isinstance(box_source, dict) and "pages" in box_source and isinstance(box_source.get("pages"), list):
        for page in box_source["pages"]:
            for box in page.get("button_boxes", []):
                if isinstance(box, dict):
                    add_box(box)
            for box in page.get("text_boxes", []):
                if isinstance(box, dict):
                    add_box(box)
    elif isinstance(box_source, dict):
        for box in box_source.get("button_boxes", []):
            if isinstance(box, dict):
                add_box(box)
        for box in box_source.get("text_boxes", []):
            if isinstance(box, dict):
                add_box(box)

    for issue in issues:
        bbox = issue.get("bounding_box")
        if bbox:
            try:
                issue_key = (
                    int(round(float(bbox.get("x")))),
                    int(round(float(bbox.get("y")))),
                    int(round(float(bbox.get("width")))),
                    int(round(float(bbox.get("height")))),
                )
            except (ValueError, TypeError, AttributeError):
                issue_key = None

            if issue_key is not None and issue_key in all_box_index:
                bounding_boxes[all_box_index[issue_key]]["score"] = issue.get("score")
            else:
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


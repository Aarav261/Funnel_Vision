from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fpdf import FPDF
from PIL import Image, ImageDraw


def generate_teardown_report(image_path: str | list[str], bounding_boxes: list[dict], flow_analysis: dict) -> str:
    image_paths = [image_path] if isinstance(image_path, str) else image_path
    image_files = [Path(path) for path in image_paths if Path(path).exists()]
    if not image_files:
        raise FileNotFoundError("No valid screenshot files found for report generation.")

    normalized_boxes: list[dict[str, Any]] = []
    for item in bounding_boxes:
        if isinstance(item, dict):
            normalized_boxes.append(item)
        elif isinstance(item, list):
            normalized_boxes.extend(box for box in item if isinstance(box, dict))

    with TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        pdf = None
        
        for image_file in image_files:
            image = Image.open(image_file).convert("RGB")
            image_width_px, image_height_px = image.size
            draw = ImageDraw.Draw(image)

            # Highlight non-selected elements in green and scored issue boxes with a heatmap.
            for box in normalized_boxes:
                x = box.get("x")
                y = box.get("y")
                width = box.get("width")
                height = box.get("height")
                if x is None or y is None or width is None or height is None:
                    continue

                score = box.get("score")
                outline_color = "#00c853"
                box_width = 5

                if score is not None:
                    try:
                        # Clamp to the expected scoring range before mapping colors.
                        score_val = max(1.0, min(10.0, float(score)))

                        if score_val <= 5.0:
                            # 1 to 5: red to yellow
                            r = 255
                            g = int(((score_val - 1.0) / 4.0) * 255)
                            b = 0
                        else:
                            # 5 to 10: yellow to green
                            r = int(((10.0 - score_val) / 5.0) * 255)
                            g = 255
                            b = 0

                        outline_color = f"#{r:02x}{g:02x}{b:02x}"
                        # Lower score = thicker border.
                        box_width = max(3, int(14 - score_val))
                    except (ValueError, TypeError):
                        outline_color = "#ff3b30"
                        box_width = 5

                draw.rectangle(
                    (float(x), float(y), float(x) + float(width), float(y) + float(height)),
                    outline=outline_color,
                    width=box_width,
                )

            # Draw a compact legend in the top-right corner for color interpretation.
            legend_width = 330
            legend_height = 130
            legend_margin = 20
            legend_x0 = max(10, image_width_px - legend_width - legend_margin)
            legend_y0 = legend_margin
            legend_x1 = legend_x0 + legend_width
            legend_y1 = legend_y0 + legend_height

            draw.rectangle((legend_x0, legend_y0, legend_x1, legend_y1), fill="#ffffff", outline="#666666", width=2)
            draw.text((legend_x0 + 10, legend_y0 + 8), "Bounding Box Legend", fill="#111111")

            legend_items = [
                ("#ff0000", "Low score (needs most work)"),
                ("#ffff00", "Mid score (some optimization needed)"),
                ("#00ff00", "High score (strong element)"),
                ("#00c853", "Not selected by Claude"),
            ]

            for idx, (color, label) in enumerate(legend_items):
                y = legend_y0 + 30 + (idx * 22)
                draw.rectangle((legend_x0 + 10, y, legend_x0 + 28, y + 14), fill=color, outline="#333333", width=1)
                draw.text((legend_x0 + 36, y - 1), label, fill="#111111")

            # Calculate dynamic PDF values to render the whole image continuously
            pdf_width_mm = 210 # Standard width
            margin = 10
            content_width_mm = pdf_width_mm - (margin * 2)
            
            # Calculate exact height needed in mm to maintain aspect ratio
            aspect_ratio = image_height_px / image_width_px
            content_height_mm = content_width_mm * aspect_ratio
            
            # Save the full drawn image temporarily
            marked_path = tmp_dir_path / "marked_full.png"
            image.save(marked_path)

            if pdf is None:
                # Re-initialize PDF with dynamic continuous height
                pdf = FPDF(format=(pdf_width_mm, content_height_mm + margin * 2 + 15))
                pdf.set_auto_page_break(auto=False)
                pdf.add_page()
                
                # Add Title
                pdf.set_font("Helvetica", "B", 18)
                pdf.cell(0, 12, "FunnelVision Teardown Report", new_x="LMARGIN", new_y="NEXT", align="C")
            else:
                pdf.add_page(format=(pdf_width_mm, content_height_mm + margin * 2 + 15))
            
            # Insert the single continuous image
            pdf.image(str(marked_path), x=margin, y=pdf.get_y(), w=content_width_mm)

    # Text section fundamentally removed to render Claude analysis natively in Streamlit UI instead
    
    output_path = Path("teardown_report.pdf")
    pdf.output(str(output_path))
    return str(output_path)

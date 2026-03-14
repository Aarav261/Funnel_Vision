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

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "FunnelVision Teardown Report", new_x="LMARGIN", new_y="NEXT", align="C")

    with TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        pdf_page_index = 1
        
        for image_file in image_files:
            image = Image.open(image_file).convert("RGB")
            image_width_px, image_height_px = image.size
            draw = ImageDraw.Draw(image)

            # Draw ALL bounding boxes onto the full image first!
            for box in normalized_boxes:
                x = box.get("x")
                y = box.get("y")
                width = box.get("width")
                height = box.get("height")
                if x is None or y is None or width is None or height is None:
                    continue

                score = box.get("score")
                outline_color = "red"
                box_width = 5

                # Heat map: 0 or low is bad (red, thickest), 10 is good (green, thinnest)
                if score is not None:
                    try:
                        score_val = float(score)
                        
                        # Bright heat map encoding
                        if score_val <= 5:
                            # 0 to 5: Solid Red to Bright Yellow
                            r = 255
                            g = int((score_val / 5.0) * 255)
                            b = 0
                        else:
                            # 5 to 10: Bright Yellow to Solid Green
                            r = int(((10.0 - score_val) / 5.0) * 255)
                            g = 255
                            b = 0
                        
                        outline_color = f"#{r:02x}{g:02x}{b:02x}"
                        
                        # Calculate width: Lower score = much thicker border
                        box_width = max(3, int(15 - (score_val * 1.2)))
                    except (ValueError, TypeError):
                        pass

                draw.rectangle(
                    (float(x), float(y), float(x) + float(width), float(y) + float(height)),
                    outline=outline_color,
                    width=box_width,
                )

            # Calculate ideal slice height to fit the PDF page perfectly
            content_width_mm = pdf.w - pdf.l_margin - pdf.r_margin
            content_height_mm = pdf.h - pdf.t_margin - pdf.b_margin - 10  # 10mm for the title cell
            
            # Ratio of PDF content height to width
            aspect_ratio = content_height_mm / content_width_mm
            slice_height_px = max(100, int(image_width_px * aspect_ratio))
            
            segment_top = 0
            while segment_top < image_height_px:
                segment_bottom = min(segment_top + slice_height_px, image_height_px)
                slice_img = image.crop((0, segment_top, image_width_px, segment_bottom))

                marked_path = tmp_dir_path / f"marked_slice_{pdf_page_index:03d}.png"
                slice_img.save(marked_path)

                if pdf_page_index > 1:
                    pdf.add_page()

                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, f"Screenshot Part {pdf_page_index}", new_x="LMARGIN", new_y="NEXT")
                pdf.image(str(marked_path), x=pdf.l_margin, y=pdf.get_y(), w=content_width_mm)

                segment_top = segment_bottom
                pdf_page_index += 1

    pdf.add_page()
    pdf.set_font("Helvetica", "", 12)

    friction_text = flow_analysis.get("F") or flow_analysis.get("Friction") or ""
    legitimacy_text = flow_analysis.get("L") or flow_analysis.get("Legitimacy") or ""
    offer_clarity_text = flow_analysis.get("O") or flow_analysis.get("Offer Clarity") or ""
    willingness_text = flow_analysis.get("W") or flow_analysis.get("Willingness to Buy") or ""

    sections = [
        ("Friction", friction_text),
        ("Legitimacy", legitimacy_text),
        ("Offer Clarity", offer_clarity_text),
        ("Willingness to Buy", willingness_text),
    ]

    for title, text in sections:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 12)
        pdf.multi_cell(0, 7, str(text).strip() if text else "")
        pdf.ln(2)

    output_path = Path("teardown_report.pdf")
    pdf.output(str(output_path))
    return str(output_path)

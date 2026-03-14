import os
import json
import base64
import io
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from PIL import Image

from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

load_dotenv()

class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int

class FlowIssue(BaseModel):
    element_name: str
    bounding_box: BoundingBox
    category: str = Field(description="Must be Friction, Legitimacy, Offer Clarity, or Willingness to Buy")
    score: int = Field(ge=1, le=10)
    suggested_text_fix: str

class FunnelTeardown(BaseModel):
    issues: list[FlowIssue] = Field(description="A list of specific FLOW framework optimization issues found on the page.")

async def main():
    # 1. Load context from scrape_results.json
    scrape_path = Path("scrape_results.json")
    if not scrape_path.exists():
        print("scrape_results.json not found")
        return
        
    with open(scrape_path, "r", encoding="utf-8") as f:
        scrape_data = json.load(f)
        
    # Extract bounding box info to feed to the LLM (to avoid overloading context)
    agentql_data = scrape_data.get("collect_text_and_button_boxes", {})
    
    # 2. Get the screenshot from page_screenshots
    screenshots_dir = Path("page_screenshots")
    images = list(screenshots_dir.glob("*.png"))
    if not images:
        print("No screenshots found in page_screenshots")
        return
        
    image_path = images[0]
    print(f"Using image: {image_path}")
    
    # Compress the image so it fits under Claude's payload limits
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Claude limits dimensions to 8000px max
        max_dim = 8000
        if img.height > max_dim or img.width > max_dim:
            if img.height > img.width:
                new_height = max_dim
                new_width = int(img.width * (max_dim / img.height))
            else:
                new_width = max_dim
                new_height = int(img.height * (max_dim / img.width))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
    image_url = f"data:image/jpeg;base64,{image_data}"

    print("Analyzing with Claude 3.5 Sonnet...")
    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=8192)
    structured_llm = llm.with_structured_output(FunnelTeardown)
    
    prompt_text = f"""You are a CRO expert analyzing this landing page. 
    
We help online small business owners increase their sales by identifying and fixing friction and credibility gaps in their funnels.

Use the FLOW Framework:
Friction
Legitimacy (Credibility)
Offer Clarity
Willingness to Buy (Trust & Risk Reversal)

4 MAJOR FUNCTIONS TO ANALYZE:

1. Primary CTA Friction 
- Whether the CTA is visible
- Reducing decision fatigue by removing excessive, repetitive or competing CTAs
- Removing steps from flow
- Increasing ease of navigation and purpose

2. Social Proof (Legitimacy)
- Presence of testimonials
- Strength & measurability of testimonials
- Presence of case studies or 'screenshot success' (rather than typed testimonials)
- Established credibility through presence of personal introduction and describing relevant experience and qualifications

3. Offer Clarity & Messaging
- Clarity of headlines
- Logical flow of copy and relevant bolding for people who skim
- Clearly emphasising the transformation or outcome of the product
- Clear 'Ideal Customer Avatar' (ICA) targeted 
- Rhetoric - persuasion through emotion, logic and credibility
- Emphasis of investment in long-term results & outcomes

4. Trust & Risk Reversal (Willingness to Buy)
- Presence of FAQ section
- Addressing common objections through messaging implicitly
- Transparent explanation of next steps
- Clear risk-reduction or refund language
- Presence of satisfaction guarantee

Analyze the provided page using the following agentql bounding box data: {json.dumps(agentql_data)}

IMPORTANT: You must return a JSON object containing exactly one key named 'issues' that contains a list of your analysis items. Each item must map perfectly to the Pydantic schema provided."""

    message = HumanMessage(content=[
        {
            "type": "text",
            "text": prompt_text
        },
        {
            "type": "image_url",
            "image_url": {"url": image_url}
        }
    ])
    
    result = await structured_llm.ainvoke([message])
    
    output_path = Path("flow_analysis.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))
        
    print(f"✅ Analysis complete! Saved to {output_path}")

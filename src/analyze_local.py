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
        
        # Claude limits dimensions to 8000px max, but 4000px is faster and cheaper
        max_dim = 4000
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
    
    prompt_text = f"""You are a top-tier Conversion Rate Optimization (CRO) expert analyzing a landing page.
Your goal is to help small business owners increase their sales by identifying friction points and credibility gaps. Keep your tone encouraging and considerate; they are trying their best!

Analyze the page based on the FLOW Framework:
1. Friction (Primary CTA visibility, clear navigation, reduced decision fatigue)
2. Legitimacy/Social Proof (Testimonials, case studies, personal bios, established authority)
3. Offer Clarity (Headline clarity, logical flow, specific ideal audience, clear transformation)
4. Willingness to Buy/Trust (FAQs, objection handling, transparent next steps, risk reversal/guarantees)

Here is the AgentQL bounding box layout data to reference: {json.dumps(agentql_data)}

HIGH-CONVERTING PRINCIPLES TO KEEP IN MIND:
- Offer simplicity and speed to measurable results.
- Create contrast against "the old way".
- Transfer authority and emphasize relatable peer success.
- Stack value so the price seems negligible.
- Maintain momentum with frequent, visible buy buttons (especially 'above the fold' and near testimonials).
- Break up text with strong visual elements and negative space.
- Address objections directly and clear barriers.

SCORING GUIDELINES & CONSTRUCTIVE FEEDBACK:
Provide scores from 1-10 with a balanced, extremely lenient approach:
- 1-4: Critical failures or entirely missing essential components (Use sparingly).
- 5-7: Functional, decent, but could use optimization (Average score for passing elements).
- 8-10: Excellent, clear, and highly persuasive implementations.

For every issue found, provide a highly specific, actionable `suggested_text_fix` on how to improve it while praising and highlighting what they did right (if anything). 
Dont use generic suggestions like "Make the headline clearer" - be specific: "The headline should explicitly mention the transformation and ideal audience, e.g. 'Helping Busy Coaches Get More Clients with Less Tech Hassle'".
Dont use dashes or arrows in your suggestions as they can cause encoding issues in the PDF generation.
IMPORTANT: You must return a JSON object with exactly one key named 'issues'. Each item must map perfectly to the requested Pydantic schema."""

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

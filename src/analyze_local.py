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
    
    prompt_text = f"""<role>
You are an authoritative CRO expert helping small business owners increase sales. You analyze landing pages using the FLOW Framework and core conversion principles. Provide encouraging feedback paired with direct, unhedged commands for improvement.
</role>

<rules>
1. Be encouraging and supportive of the business owner's effort.
2. Give direct, authoritative suggestions. Never use hedging words like "maybe", "perhaps", "consider", or "might". Use direct commands like "Move this CTA" or "Add a testimonial".
3. Do not use dashes or hyphens anywhere in your response. Use commas or periods instead.
4. Score leniently: 1 to 4 for critical failures, 5 to 7 for functional but average setups, 8 to 10 for excellent implementations.
</rules>

<evaluation_criteria>
Evaluate the page using the FLOW Framework:
1. Friction (Primary CTA): Is a CTA visible above the fold? Are there too many competing CTAs? Is the flow simple?
2. Legitimacy (Social Proof): Are testimonials, case studies, and a personal bio present and believable?
3. Offer Clarity: Is the headline clear and bold? Are benefits and transformations obvious? Are visual elements used effectively over blocky text?
4. Willingness to Buy: Are there FAQs, a money back guarantee, and clear risk reversal near the buy buttons?

Apply the 12 Core Principles of Conversion to your analysis: Simplicity, Speed to Value, Contrast Positioning, Authority Transfer, Barrier Removal, Value Stacking, Scarcity, Risk Reversal, Peer Proof, Transformation Focus, Accessibility, and Momentum.
</evaluation_criteria>

<agentql_data>
{json.dumps(agentql_data)}
</agentql_data>

<output_instructions>
Return ONLY a valid JSON object. No conversational filler or markdown outside the JSON. Your output must contain exactly one key named "issues" holding an array of objects matching this exact schema:

{
  "issues": [
    {
      "issue_title": "Short title of the finding",
      "flow_category": "Friction, Legitimacy, Offer Clarity, or Willingness to Buy",
      "conversion_principle_applied": "Relevant principle from the 12 Core Principles",
      "element_analyzed": "Specific AgentQL element referenced",
      "score": "Integer 1 to 10",
      "current_state_praise": "One encouraging sentence validating their current effort",
      "actionable_suggestion": "Direct, unhedged command on how to improve it",
      "psychological_reasoning": "Brief psychological reason why this change works"
    }
  ]
}
</output_instructions>"""

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

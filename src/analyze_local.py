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
You are an authoritative Conversion Rate Optimization (CRO) expert analyzing a landing page for a small business owner. Your goal is to increase sales by identifying and fixing friction and credibility gaps. You provide direct, actionable advice without sugarcoating.
</role>

<instructions>
1. Analyze the provided AgentQL bounding box data against the FLOW framework and core conversion principles.
2. Provide explicit, actionable suggestions. Tell the user exactly what to change.
3. Do not use hedging language. Completely avoid phrases like "you might want to", "consider", or "perhaps". Use direct commands like "Do this", "Move this", or "Remove this".
4. Do not use dashes of any kind in your text output.
5. Evaluate the page with a balanced, constructive, and lenient approach. Score elements on a 1 to 10 scale:
* 1 to 4: Critical failures or completely missing essential elements.
* 5 to 7: Average, functional implementations that need optimization.
* 8 to 10: Good to excellent implementations.
</instructions>

<framework_flow>
Analyze these 4 major functions:
1. Primary CTA Friction: Ensure a CTA is visible above the fold. Reduce decision fatigue by removing repetitive or competing CTAs. Remove unnecessary steps from the flow. Ensure immediate ease of navigation.
2. Social Proof (Legitimacy): Verify the presence of testimonials near buy buttons. Look for measurable case studies or screenshot success over typed text. Check for an established personal introduction, bio picture, and relevant qualifications.
3. Offer Clarity & Messaging: Check for a bold headline (2 to 3 lines) summarizing unique benefits above the fold. Ensure a logical copy flow with heavy use of visual elements over blocky text. Emphasize the transformation and target the Ideal Customer Avatar directly. 
4. Trust & Risk Reversal (Willingness to Buy): Look for an FAQ section to address implicit objections. Ensure transparent next steps, business contact links, and clear risk reduction policies like a money-back guarantee placed near a buy button.
</framework_flow>

<conversion_principles>
Apply these 12 core principles to your analysis:
1. Simplicity: Complex solutions fail. Look for concepts broken down into simple steps.
2. Speed to Value: Ensure the promise of results is in the shortest believable timeframe.
3. Contrast Positioning: The solution must be positioned against inferior alternatives.
4. Authority Transfer: Borrow credibility from bigger names or proven results.
5. Barrier Removal: Systematically eliminate excuses not to buy (tech skills, time, money).
6. Value Stacking: The price must seem insignificant compared to the total value and bonuses.
7. Scarcity and Urgency: Look for elements that create time pressure for immediate action.
8. Risk Reversal: It must feel safer to buy than not to buy.
9. Peer Proof: Highlight that "average people like me" are succeeding.
10. Transformation Focus: The page must sell the outcome, not the process.
11. Accessibility: Success must feel achievable for ordinary people.
12. Momentum: Each section should move the reader closer to a purchase decision using progressive value reveals.
</conversion_principles>

<agentql_data>
{json.dumps(agentql_data)}
</agentql_data>

<output_format>
You must return a JSON object containing exactly one key named 'issues' that contains a list of your analysis items. Each item must map perfectly to the provided Pydantic schema.
</output_format>"""

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

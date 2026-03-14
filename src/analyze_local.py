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

12 CORE PRINCIPLES THAT MAKE OFFERS CONVERT
1. THE SIMPLICITY PRINCIPLE
Core Concept: Complex solutions don't sell; simple ones do.
Application: Everything is broken down to "3 steps," "60 minutes," or "just copy and paste"
Psychology: Overwhelmed people crave simplicity and quick wins
Evidence: Every offer emphasizes "no tech skills," "no experience needed," "plug-and-play"
Why It Works: Reduces cognitive load and perceived effort required

2. THE SPEED-TO-VALUE PRINCIPLE
Core Concept: Promise results in the shortest believable timeframe.
Application: "60 minutes," "24 hours," "2-day launches," "instant access"
Psychology: Instant gratification beats delayed satisfaction
Evidence: All offers emphasize rapid implementation and quick results
Why It Works: Matches modern attention spans and desire for immediate progress

3. THE CONTRAST POSITIONING PRINCIPLE
Core Concept: Position your solution against inferior alternatives.
Application: Old way vs. new way, myths vs. facts, most people vs. smart people
Psychology: Creates tribal identity and intellectual superiority
Evidence: Every page has detailed comparisons showing their method as evolved/superior
Why It Works: Makes buyers feel smart and forward-thinking for choosing you

4. THE AUTHORITY TRANSFER PRINCIPLE
Core Concept: Borrow credibility from bigger names and proven results.
Application: "Same system that made me $6M," "clients include Tony Robbins," "600+ funnels built"
Psychology: People follow proven winners and established authorities
Evidence: All creators prominently display their biggest wins and famous clients
Why It Works: Reduces risk perception through social proof of success

5. THE BARRIER REMOVAL PRINCIPLE
Core Concept: Systematically eliminate every excuse not to buy.
Application: Address tech skills, audience size, experience, time, money objections
Psychology: People look for reasons NOT to take action; remove them all
Evidence: Extensive "no [objection] required" sections on every page
Why It Works: Clears the path to purchase by removing friction points

6. THE VALUE STACKING PRINCIPLE
Core Concept: Make the price seem ridiculously small compared to total value.
Application: $1,700+ value for $27, multiple bonuses with individual pricing
Psychology: Loss aversion - fear of missing out on massive value
Evidence: Every offer shows crossed-out higher prices and bonus values
Why It Works: Creates perception of getting an incredible deal

7. THE SCARCITY/URGENCY PRINCIPLE
Core Concept: Create time pressure to force immediate action.
Application: Countdown timers, limited quantities, price increases, bonus removal
Psychology: Scarcity increases perceived value and forces decisions
Evidence: All pages have multiple urgency elements throughout
Why It Works: Overcomes procrastination and "I'll think about it" responses

8. THE RISK REVERSAL PRINCIPLE
Core Concept: Make it safer to buy than not to buy.
Application: Money-back guarantees, "keep it even if you refund," proof requirements
Psychology: Removes purchase anxiety and fear of making wrong decision
Evidence: Strong guarantees with unique twists on every offer
Why It Works: Shifts risk from buyer to seller, enabling easier decisions

9. THE PEER PROOF PRINCIPLE
Core Concept: Show that "people like me" are succeeding with this.
Application: Specific customer results, testimonials, success stories with photos
Psychology: Social proof from similar people is more convincing than expert endorsements
Evidence: Extensive customer success sections with real names and results
Why It Works: Provides relatable examples of success, making it feel achievable

10. THE TRANSFORMATION FOCUS PRINCIPLE
Core Concept: Sell the outcome, not the process or features.
Application: Focus on "what you'll become" rather than "what you'll learn"
Psychology: People buy better versions of themselves, not information
Evidence: Headlines emphasize transformation: "turn into," "become," "go from X to Y"
Why It Works: Connects to deeper emotional desires for change and improvement

11. THE ACCESSIBILITY PRINCIPLE
Core Concept: Make success feel achievable for ordinary people.
Application: "Average people making thousands," "even if you're a beginner," "anyone can do this"
Psychology: Aspirational but attainable - not so easy it's worthless, not so hard it's impossible
Evidence: Success stories feature "regular people," not just experts or celebrities
Why It Works: Builds confidence that the buyer can achieve similar results

12. THE MOMENTUM PRINCIPLE
Core Concept: Create psychological momentum toward the purchase decision.
Application: Multiple CTAs, progressive value reveals, building excitement throughout
Psychology: Each section should move the reader closer to "yes"
Evidence: Strategic placement of buy buttons and value reveals throughout the page
Why It Works: Maintains engagement and builds commitment through the sales process


HOW THESE PRINCIPLES WORK TOGETHER:
THE PSYCHOLOGICAL JOURNEY:
Hook (Simplicity + Speed) → "This looks easy and fast"
Contrast (Positioning + Authority) → "This is clearly better than alternatives"
Proof (Peer + Transformation) → "People like me are getting results"
Value (Stacking + Accessibility) → "This is an incredible deal I can actually use"
Safety (Risk Reversal + Barrier Removal) → "There's no real risk in trying this"
Urgency (Scarcity + Momentum) → "I need to act now"
THE CONVERSION FORMULA:
High Conversion = (Desire × Credibility × Urgency) ÷ (Friction × Risk)
Desire: Created through transformation focus and contrast positioning
Credibility: Built through authority transfer and peer proof
Urgency: Generated through scarcity and momentum techniques
Friction: Reduced through simplicity and barrier removal
Risk: Minimized through risk reversal and accessibility

WHY THESE OFFERS CONVERT SO WELL:
2. HIGH PERCEIVED VALUE
Massive value stacks make price seem insignificant
Bonuses often worth more than the main offer
Creates "no-brainer" purchasing decisions
3. IMMEDIATE GRATIFICATION
Instant access satisfies need for immediate results
Digital delivery removes shipping delays
Can start benefiting right away
4. SOCIAL PROOF ABUNDANCE
Easy to get testimonials at low price points
More people willing to try = more success stories
Creates viral social proof effect
5. IMPULSE PURCHASE PSYCHOLOGY
Price point triggers impulse buying behavior
Less deliberation required than high-ticket items
Emotional decisions rather than logical analysis
THE META-PRINCIPLE: EMOTIONAL RESONANCE
The overarching principle: All successful low-ticket offers tap into deep emotional drivers:
Fear of Missing Out (FOMO)
Desire for Transformation
Need to Belong (to the "smart" group)
Craving for Simplicity (in a complex world)
Hope for Quick Wins (after past failures)
Pride in Making Smart Decisions
These 12 principles work because they address fundamental human psychology while removing barriers to action. They make the purchase feel inevitable, intelligent, and emotionally satisfying - which is the ultimate goal of any high-converting sales page.

SALES PAGE INFORMATION:

CTA:
So when you open a sales page what you see on the screen (the top of sales page’ is called ‘above the fold. So before scrolling. There should be a CTA visible on that top part, so people that know they want to buy can do so without scrolling to find another CTA. Makes it easy for those quick decision makers. 

Need to ensure that somewhere on the sales page that outlines how this product is different to others

Sales pages are the first impressions of your offers

You need to be able to convey the value of your offer on your sales page.

Sales and marketing is all about perception. How people perceive the product before buying it is very important!

Principles behind top offers

“Above the fold" = what people see on your page before they scroll down

You want people to immediately grasp the overall concept of your offer

You need a key bold headline that summarises the key benefits of your product offers and talks about how it’s unique or different (only 2-3 lines)

Understand what you product is, what it does, and who its for

You also need some sort of visual at the top of the page (e.g. mockups, video etc)

Make heavy use of visual elements

Any social proof should be relatively towards the top of the page

Heavy use of visuals as you move down the page. Show, don’t tell using a graphic rather than just text

A lot of testimonials and proof right near the buy button

You want to have a buy button every single section

Put a buy button right near testimonials

You also need sections to break down the product with more detail
E.g. You will get this which will help you do this - how this research will help you receive This, this and this

You need a buy button in any spot on the page where a prospective customer may want to make a buying decision

You need a section of your website that explains why your product, system or service solves the problem your audience is facing

Include at least one picture of yourself on your sales page to show that you are a real human - it humanises you and improves the relationship

Make heavy use of visual elements 

If you don’t have much social proof, you can talk about how someone else found success doing something a certain way i.e. in a way that reflects your service or offering

You can leverage social proof from other sources until you have your own client testimonials

Include some bonuses where possible to make it a no-brainer

You want to have some sort of money back guarantee on the page with a buy button right near it

It’s really important that on your page you have a disclaimer, privacy policy, terms of service and a contact link on your page. Your business information etc.

There are quick links at the top of the page that lead to the checkout of the purchase

It doesn’t have to be that complicated

Top of the page shows a simple headline, with a visual showing the offer right in front, as well as a button to buy ‘above the fold’

You want to make your offer feel as tangible, real and physical as possible

You have social proof immediately near the top of the page

Sell to the average person who can’t relate to millionaires

Demonstrate the key benefits of how the product will help them

Shows how the products can apply to different desires

You need to address objections by showing whether this will work for you (the ideal audience)

Have a bio and a picture which is good for the sales page

Can sometimes be useful to give a sneak peak of a product

Have some questions and answers towards the end of the sales page at all.

You don’t want people to be confused about what they are getting on a sales page

You don’t want people to be guessing what is included or having to read every single word on the sale page to understand what they are purchasing. 

Remember - A confused mind doesn’t buy

There should be a lot of images, and not too much blocky text

You want to have a lot of negative space and images

Above the fold we have visual elements, social proof, a large bold headline telling you exactly what this is and who it is for

Emphasise speed and ease of implementation

Break up the page with images

Some people are scanners while others will read every page

Ask yourself what questions people will ask when you enter the page, and then consider these concerns in the Q&A or answer them as they scroll down the page

There should be lots of buy buttons

Put a summary of the offer at the bottom

The most successful offers promise to remove barriers

You want to convince the person that the product is worth a lot more than wha you are actually selling it for

You might even include freebies and highlight their value e.g. Usually $37, now FREE

And the same with the high ticket offering. If you value it as over $5000 and are selling it for $2000, highlight that (or make it feel like an increased urgency for a sale)

Explain the cost of not taking action to the prospective consumer

SCORING GUIDELINES & LENIENCY:
Please evaluate the page with a balanced, constructive, and lenient approach. Do not be overly strict. 
- Scores of 1-4 should be reserved ONLY for critical failures, huge friction points, or completely missing essential elements.
- Scores of 5-7 are for average, standard, or decent implementations that are functional but could use some optimization.
- Scores of 8-10 are for good, very good, and excellent implementations.
Most small business owners are doing their best, so be encouraging. If an element is present and functionally does its job (even if it's not perfect CRO), give it a passing score (5+).

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

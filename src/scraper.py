import agentql
import logging
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

def _build_screenshot_path(url: str, index: int, scroll_index: int | None = None) -> Path:
    parsed = urlparse(url)
    host = parsed.netloc.replace(":", "_").replace(".", "_") or "page"
    path = parsed.path.strip("/").replace("/", "_") or "home"
    output_dir = Path("page_screenshots")
    output_dir.mkdir(parents=True, exist_ok=True)
    if scroll_index is None:
        return output_dir / f"{index:02d}_{host}_{path}.png"
    return output_dir / f"{index:02d}_{host}_{path}_scroll_{scroll_index:03d}.png"

async def run_full_scrape(target_url: str | list[str]) -> dict:
    target_urls = [target_url] if isinstance(target_url, str) else target_url
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
            results: list[dict] = []

            for index, url in enumerate(target_urls, start=1):
                # Optimization 2: Wait for 'load' instead of 'networkidle' (faster)
                await page.goto(url, wait_until="load", timeout=45000)
                
                viewport_height = await page.evaluate("window.innerHeight")
                scroll_height = await page.evaluate(
                    "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
                )
                y_positions = range(0, int(scroll_height), max(1, int(viewport_height)))

                # Scroll down once to trigger lazy loading
                for scroll_index, y in enumerate(y_positions, start=1):
                    await page.evaluate("(scrollY) => window.scrollTo(0, scrollY)", y)
                    await page.wait_for_timeout(200)

                # Reset to top, capture a SINGLE perfect whole-page screenshot
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(500)
                
                screenshot_path = str(_build_screenshot_path(url, index))
                await page.screenshot(path=screenshot_path, full_page=True)

                # AgentQL data
                agentql_page = await agentql.wrap_async(page)
                data = await agentql_page.query_data(
                    """
                    {
                        primary_h1
                        button_texts[]
                    }
                    """
                )
                headline = data.get("primary_h1") or ""
                buttons = data.get("button_texts") or []
                if not isinstance(buttons, list):
                    buttons = [buttons]
                buttons = [text for text in buttons if isinstance(text, str) and text.strip()]

                # Optimization 3: Batch DOM geometry extraction instantly inside JS
                boxes_data = await page.evaluate("""() => {
                    const buttonSelector = "button, [role='button'], input[type='button'], input[type='submit'], a[role='button']";
                    const textSelector = "h1, h2, h3, h4, h5, h6, p, li, span"; // no 'a' to avoid huge overlaps

                    const buttons = Array.from(document.querySelectorAll(buttonSelector));
                    const texts = Array.from(document.querySelectorAll(textSelector));
                    
                    const getBox = (el, type) => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return null;
                        
                        const style = window.getComputedStyle(el);
                        if (style.visibility === "hidden" || style.display === "none" || style.opacity === "0") return null;
                        
                        const text = el.innerText ? el.innerText.trim() : (el.value ? el.value.trim() : "");
                        if (!text) return null;
                        
                        return {
                            text: text,
                            x: Math.round(rect.x + window.scrollX),
                            y: Math.round(rect.y + window.scrollY),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            type: type
                        };
                    };

                    return {
                        button_boxes: buttons.map(el => getBox(el, "button")).filter(b => b),
                        text_boxes: texts.map(el => getBox(el, "text")).filter(b => b)
                    };
                }""")

                results.append({
                    "url": url,
                    "headline": headline,
                    "buttons": buttons,
                    "screenshot_path": screenshot_path,
                    "screenshot_paths": [screenshot_path],
                    "button_boxes": boxes_data["button_boxes"],
                    "text_boxes": boxes_data["text_boxes"],
                })

            if len(results) == 1:
                return {"scrape_page": results[0], "collect_text_and_button_boxes": results[0]}
            return {"scrape_page": {"pages": results}, "collect_text_and_button_boxes": {"pages": results}}

        finally:
            await browser.close()

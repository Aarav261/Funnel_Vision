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


async def scrape_page(target_url: str | list[str]) -> dict:
    target_urls = [target_url] if isinstance(target_url, str) else target_url
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
            results: list[dict] = []

            for index, url in enumerate(target_urls, start=1):
                await page.goto(url, wait_until="networkidle")
                viewport_height = await page.evaluate("window.innerHeight")
                scroll_height = await page.evaluate(
                    "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
                )
                y_positions = range(0, int(scroll_height), max(1, int(viewport_height)))
                screenshot_paths: list[str] = []

                for scroll_index, y in enumerate(y_positions, start=1):
                    await page.evaluate("(scrollY) => window.scrollTo(0, scrollY)", y)
                    await page.wait_for_timeout(250)

                # Reset to top, capture a SINGLE perfect whole-page screenshot
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(250)
                
                screenshot_path = str(_build_screenshot_path(url, index))
                await page.screenshot(path=screenshot_path, full_page=True)
                primary_screenshot_path = screenshot_path
                screenshot_paths = [screenshot_path]

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
                result = {
                    "url": url,
                    "headline": headline,
                    "buttons": buttons,
                    "screenshot_path": primary_screenshot_path,
                    "screenshot_paths": screenshot_paths,
                }
                logging.info("URL: %s", url)
                logging.info("Headline: %s", headline)
                logging.info("Buttons: %s", buttons)
                logging.info("Screenshots captured: %s", len(screenshot_paths))
                results.append(result)

            if len(results) == 1:
                return results[0]
            return {"pages": results}

        finally:
            await browser.close()


async def collect_text_and_button_boxes(target_url: str | list[str]) -> dict:
    target_urls = [target_url] if isinstance(target_url, str) else target_url
    button_selector = "button, [role='button'], input[type='button'], input[type='submit'], a[role='button']"
    text_selector = "h1, h2, h3, h4, h5, h6, p, li, span, a"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
            page_results: list[dict] = []

            for url in target_urls:
                await page.goto(url, wait_until="networkidle")

                viewport_height = await page.evaluate("window.innerHeight")
                scroll_height = await page.evaluate(
                    "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
                )
                y_positions = range(0, int(scroll_height), max(1, int(viewport_height)))
                
                for scroll_index, y in enumerate(y_positions, start=1):
                    await page.evaluate("(scrollY) => window.scrollTo(0, scrollY)", y)
                    await page.wait_for_timeout(250)

                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(500)

                button_boxes = []
                button_locator = page.locator(button_selector)
                button_count = await button_locator.count()
                for i in range(button_count):
                    el = button_locator.nth(i)
                    if not await el.is_visible():
                        continue
                        
                    box = await el.evaluate("""(node) => {
                        const rect = node.getBoundingClientRect();
                        return {
                            x: rect.x + window.scrollX,
                            y: rect.y + window.scrollY,
                            width: rect.width,
                            height: rect.height
                        };
                    }""")
                    text = (await el.text_content() or "").strip()
                    if box and text and box["width"] > 0 and box["height"] > 0:
                        button_boxes.append(
                            {
                                "text": text,
                                "x": box["x"],
                                "y": box["y"],
                                "width": box["width"],
                                "height": box["height"],
                                "type": "button",
                            }
                        )

                text_boxes = []
                text_locator = page.locator(text_selector)
                text_count = await text_locator.count()
                for i in range(text_count):
                    el = text_locator.nth(i)
                    if not await el.is_visible():
                        continue
                        
                    box = await el.evaluate("""(node) => {
                        const rect = node.getBoundingClientRect();
                        return {
                            x: rect.x + window.scrollX,
                            y: rect.y + window.scrollY,
                            width: rect.width,
                            height: rect.height
                        };
                    }""")
                    text = (await el.text_content() or "").strip()
                    if box and text and box["width"] > 0 and box["height"] > 0:
                        text_boxes.append(
                            {
                                "text": text,
                                "x": box["x"],
                                "y": box["y"],
                                "width": box["width"],
                                "height": box["height"],
                                "type": "text",
                            }
                        )

                page_results.append(
                    {
                        "url": url,
                        "button_boxes": button_boxes,
                        "text_boxes": text_boxes,
                    }
                )

            if len(page_results) == 1:
                return page_results[0]
            return {"pages": page_results}
        finally:
            await browser.close()

    
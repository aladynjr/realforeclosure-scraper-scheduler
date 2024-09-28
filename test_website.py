import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
async def test_website():
    # Define the auction date
    auction_date = datetime(2024, 9, 18)  # September 16, 2024
    formatted_date = auction_date.strftime("%m/%d/%Y")

    # Define proxy details
    proxy_host = 'shared-datacenter.geonode.com'
    proxy_port = '9008'
    proxy_username = os.getenv('PROXY_USERNAME')
    proxy_password = os.getenv('PROXY_PASSWORD')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            proxy={
                "server": f"http://{proxy_host}:{proxy_port}",
                "username": proxy_username,
                "password": proxy_password,
            }
        )

        context = await browser.new_context(
            viewport=None,
            no_viewport=True
        )
        page = await context.new_page()

        # Set user agent to mimic a normal browser
        await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})

        # Navigate to the target URL with the specified date
        url = f'https://manatee.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate={formatted_date}'
      #  url = f'https://manatee.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate={formatted_date}'
       # url = f'https://putnam.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate={formatted_date}'
        await page.goto(url, wait_until='networkidle')

        print(f"Browser opened and navigated to URL for auction date: {formatted_date}")
        print("Press Ctrl+C to close the browser and exit the script.")
        
        # Keep the script running indefinitely
        while True:
            await asyncio.sleep(1)
if __name__ == "__main__":
    try:
        asyncio.run(test_website())
    except KeyboardInterrupt:
        print("\nScript interrupted. Closing browser and exiting.")
import asyncio
import os
from playwright.async_api import async_playwright, TimeoutError
from bs4 import BeautifulSoup
from datetime import datetime
import random
import json
import csv
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

WEBAPP_URL = "https://script.google.com/macros/s/AKfycby0nDwiCz097tsotDrqHAEwVS10Q9_dwYnsivN02_SlhBgB7PfXW6OOnYnJV3nqjUD5Aw/exec"

def send_auction_data(auction_date, auction_items):
    ordered_fields = [
        "Auction Date", "County", "Auction Type", "Sold Amount", "Opening Bid", 
        "Excess Amount", "Case #", "Parcel ID", "Property Address", "Property City", 
        "Property State", "Property Zip", "Assessed Value", "Auction Status", 
        "Final Judgment Amount", "Plaintiff Max Bid", "Sold Date", "Sold To"
    ]

    ordered_items = []
    for item in auction_items:
        # Calculate Excess Amount
        opening_bid = float(item.get("Opening Bid", "").replace("$", "").replace(",", "") or 0)
        sold_amount = float(item.get("Sold Amount", "").replace("$", "").replace(",", "") or 0)
        excess_amount = max(0, sold_amount - opening_bid)

        ordered_item = {field: item.get(field, "") for field in ordered_fields}
        ordered_item["Excess Amount"] = f"${excess_amount:.2f}"
        ordered_items.append(ordered_item)

    data = {
        "date": auction_date,
        "items": ordered_items
    }

    try:
        response = requests.post(WEBAPP_URL, json=data)
        if response.status_code == 200:
            print(f"Successfully sent data for {len(auction_items)} items.")
            print("Response from server:")
            print(response.text)
        else:
            print(f"Failed to send data. Status code: {response.status_code}")
            print("Response from server:")
            print(response.text)
    except Exception as e:
        print(f"An error occurred while sending data: {str(e)}")

async def extract_auction_info(div):
    info = {}
    
    # Check for 3rd Party Bidder
    sold_to_elem = div.select_one('.ASTAT_MSG_SOLDTO_MSG')
    if not (sold_to_elem and sold_to_elem.text.strip() == "3rd Party Bidder"):
        return None  # Skip this item if not sold to 3rd Party Bidder
    
    # Extract auction status and details
    status_elem = div.select_one('.ASTAT_MSGA')
    if status_elem:
        info['Auction Status'] = status_elem.text.strip()
    
    sold_date_elem = div.select_one('.ASTAT_MSGB')
    if sold_date_elem:
        info['Sold Date'] = sold_date_elem.text.strip()
    
    sold_amount_elem = div.select_one('.ASTAT_MSGD')
    if sold_amount_elem:
        info['Sold Amount'] = sold_amount_elem.text.strip()
    
    info['Sold To'] = "3rd Party Bidder"
    
    details_table = div.select_one('.AUCTION_DETAILS table')
    if details_table:
        for row in details_table.select('tr'):
            label = row.select_one('.AD_LBL')
            data = row.select_one('.AD_DTA')
            if label and data:
                key = label.text.strip().rstrip(':')
                value = data.text.strip()
                if key == '':
                    # Process the location information
                    location_parts = value.split('-')
                    if len(location_parts) == 2:
                        city_state = location_parts[0].strip().split(',')
                        if len(city_state) == 2:
                            info['Property City'] = city_state[0].strip()
                            info['Property State'] = city_state[1].strip()
                        else:
                            info['Property City'] = city_state[0].strip()
                            info['Property State'] = ''
                        info['Property Zip'] = location_parts[1].strip()
                    else:
                        info['Property City'] = value
                        info['Property State'] = ''
                        info['Property Zip'] = ''
                else:
                    info[key] = value.replace('\xa0', ' ').strip()
    
    # Extract Parcel ID from the link if present
    parcel_id_link = details_table.select_one('a[href*="parid="]')
    if parcel_id_link:
        info['Parcel ID'] = parcel_id_link.text.strip()
    
    return info


def convert_to_csv(json_data, csv_filename):
    with open(csv_filename, 'w', newline='') as csvfile:
        fieldnames = [
            "Auction Date", "County", "Auction Type", "Auction Status", "Sold Date", 
            "Sold Amount", "Sold To", "Opening Bid", "Excess Amount", "Case #", 
            "Parcel ID", "Property Address", "Property City", "Property State", "Property Zip",
            "Assessed Value", "Certificate #"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        auction_date = json_data["auction_date"]
        for item in json_data["auction_items"]:
            opening_bid = item.get("Opening Bid", "").replace("$", "").replace(",", "")
            opening_bid = float(opening_bid) if opening_bid else 0.0

            sold_amount = item.get("Sold Amount", "").replace("$", "").replace(",", "")
            sold_amount = float(sold_amount) if sold_amount else 0.0

            excess_amount = max(0, sold_amount - opening_bid)

            writer.writerow({
                "Auction Date": auction_date,
                "County": "Manatee",
                "Auction Type": item.get("Auction Type", ""),
                "Auction Status": item.get("Auction Status", ""),
                "Sold Date": item.get("Sold Date", ""),
                "Sold Amount": item.get("Sold Amount", ""),
                "Sold To": item.get("Sold To", ""),
                "Opening Bid": item.get("Opening Bid", ""),  # Use the original string value
                "Excess Amount": f"{excess_amount:.2f}",
                "Case #": item.get("Case #", ""),
                "Parcel ID": item.get("Parcel ID", ""),
                "Property Address": item.get("Property Address", ""),
                "Property City": item.get("Property City", ""),
                "Property State": item.get("Property State", ""),
                "Property Zip": item.get("Property Zip", ""),
                "Assessed Value": item.get("Assessed Value", ""),
                "Certificate #": item.get("Certificate #", "")
            })
def process_and_save_auction_data(all_auction_info, auction_date, json_filename, csv_filename):
    primary_fields = [
        "Auction Date", "County", "Auction Type", "Sold Amount", "Opening Bid", 
        "Excess Amount", "Case #", "Parcel ID", "Property Address", "Property City", 
        "Property State", "Property Zip"
    ]

    processed_items = []
    for item in all_auction_info:
        opening_bid = float(item.get("Opening Bid", "").replace("$", "").replace(",", "") or 0)
        sold_amount = float(item.get("Sold Amount", "").replace("$", "").replace(",", "") or 0)
        excess_amount = max(0, sold_amount - opening_bid)

        processed_item = {
            "Auction Date": auction_date,
            "County": "Manatee",
            "Auction Type": item.get("Auction Type", ""),
            "Sold Amount": item.get("Sold Amount", ""),
            "Opening Bid": item.get("Opening Bid", ""),
            "Excess Amount": f"{excess_amount:.2f}",
            "Case #": item.get("Case #", ""),
            "Parcel ID": item.get("Parcel ID", ""),
            "Property Address": item.get("Property Address", ""),
            "Property City": item.get("Property City", ""),
            "Property State": item.get("Property State", ""),
            "Property Zip": item.get("Property Zip", ""),
            **{k: v for k, v in item.items() if k not in primary_fields}
        }
        processed_items.append(processed_item)

    # Save JSON
    output_data = {
        "auction_date": auction_date,
        "total_items": len(processed_items),
        "auction_items": processed_items
    }
    with open(json_filename, 'w') as json_file:
        json.dump(output_data, json_file, indent=2)

    # Save CSV
    all_fields = primary_fields + sorted(set(k for item in processed_items for k in item.keys()) - set(primary_fields))
    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=all_fields)
        writer.writeheader()
        writer.writerows(processed_items)

    print(f"Auction data saved to {json_filename} and {csv_filename}")
async def run_scraper(auction_date=None):
    if auction_date is None:
        auction_date = datetime(2024, 9, 16)
    formatted_date = auction_date.strftime("%m/%d/%Y")

    proxy_host = 'shared-datacenter.geonode.com'
    proxy_port = '9008'
    proxy_username = os.getenv('PROXY_USERNAME')
    proxy_password = os.getenv('PROXY_PASSWORD')

    # Create directories if they don't exist
    os.makedirs('screenshots', exist_ok=True)
    os.makedirs('results', exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={
                "server": f"http://{proxy_host}:{proxy_port}",
                "username": proxy_username,
                "password": proxy_password,
            }
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            java_script_enabled=True,
            ignore_https_errors=True,
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            }
        )
        # Firefox doesn't need the webdriver property modification
        # so we can remove the init script

        page = await context.new_page()

        url = f'https://manatee.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate={formatted_date}'
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(random.uniform(2, 5))  # Random delay
            await page.screenshot(path='screenshots/initial_load.png', full_page=True)
            print("Screenshot saved: screenshots/initial_load.png")

            # Check for 403 Forbidden
            page_content = await page.content()
            if '403 Forbidden' in page_content:
                print("Error: 403 Forbidden. Access denied.")
                await page.screenshot(path='screenshots/403_forbidden_error.png', full_page=True)
                print("Screenshot saved: screenshots/403_forbidden_error.png")
                await browser.close()
                return

        except TimeoutError:
            print(f"Timeout while loading the page. URL: {url}")
            await page.screenshot(path='screenshots/timeout_error.png', full_page=True)
            print("Screenshot saved: screenshots/timeout_error.png")
            await browser.close()
            return

        all_auction_info = []
        current_page = 0

        while True:
            current_page += 1
            
            try:
                await page.wait_for_selector('div.AUCTION_ITEM', timeout=30000)
                await asyncio.sleep(random.uniform(1, 3))  # Random delay
                await page.screenshot(path=f'screenshots/page_{current_page}_items_loaded.png', full_page=True)
                print(f"Screenshot saved: screenshots/page_{current_page}_items_loaded.png")
            except TimeoutError:
                print(f"No auction items found on page {current_page}. Ending pagination.")
                await page.screenshot(path=f'screenshots/page_{current_page}_no_items.png', full_page=True)
                print(f"Screenshot saved: screenshots/page_{current_page}_no_items.png")
                break

            area_c_content = await page.inner_html('#Area_C')
            soup = BeautifulSoup(area_c_content, 'html.parser')
            auction_items = soup.select('div.AUCTION_ITEM')

            if not auction_items:
                print(f"No auction items found on page {current_page} after parsing. Ending pagination.")
                await page.screenshot(path=f'screenshots/page_{current_page}_no_items_after_parsing.png', full_page=True)
                print(f"Screenshot saved: screenshots/page_{current_page}_no_items_after_parsing.png")
                break

            for item in auction_items:
                info = await extract_auction_info(item)
                if info:  # Only add items sold to 3rd Party Bidder
                    all_auction_info.append(info)

            try:
                max_page_element = await page.wait_for_selector('#maxCA', timeout=5000)
                max_page = await max_page_element.inner_text()
                max_page = int(max_page)
            except TimeoutError:
                print("Couldn't find max page number. Ending pagination.")
                await page.screenshot(path=f'screenshots/page_{current_page}_no_max_page.png', full_page=True)
                print(f"Screenshot saved: screenshots/page_{current_page}_no_max_page.png")
                break

            print(f"Processed page {current_page} of {max_page}")

            if current_page < max_page:
                try:
                    next_page_button = await page.wait_for_selector('#BID_WINDOW_CONTAINER > div.Head_C > div:nth-child(3) > span.PageRight', timeout=5000)
                    await next_page_button.click()
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_function(f'document.querySelector("#curPCA").getAttribute("curpg") == "{current_page + 1}"', timeout=10000)
                    await asyncio.sleep(random.uniform(2, 4))  # Random delay
                    await page.screenshot(path=f'screenshots/page_{current_page + 1}_after_navigation.png', full_page=True)
                    print(f"Screenshot saved: screenshots/page_{current_page + 1}_after_navigation.png")
                except TimeoutError:
                    print(f"Timeout while navigating to page {current_page + 1}. Ending pagination.")
                    await page.screenshot(path=f'screenshots/page_{current_page + 1}_navigation_error.png', full_page=True)
                    print(f"Screenshot saved: screenshots/page_{current_page + 1}_navigation_error.png")
                    break
            else:
                break

        for item in all_auction_info:
            item["Auction Date"] = formatted_date
            item["County"] = "Manatee"

        # Prepare data for JSON output
        output_data = {
            "auction_date": formatted_date,
            "total_items": len(all_auction_info),
            "auction_items": all_auction_info
        }


        json_filename = f"results/auction_data_{formatted_date.replace('/', '-')}.json"
        csv_filename = f"results/auction_data_{formatted_date.replace('/', '-')}.csv"

        process_and_save_auction_data(all_auction_info, formatted_date, json_filename, csv_filename)

        # Send data to Google Spreadsheet
        print("\nSending data to Google Spreadsheet...")
        send_auction_data(formatted_date, all_auction_info)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
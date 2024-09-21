import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright
import aiohttp
from bs4 import BeautifulSoup
import aiofiles
import csv
import os
import requests
from dotenv import load_dotenv
import pytz
from datetime import date
import re

try:
    from main import get_logger
    logger = get_logger()
except ImportError:
    logger = None

import time
# Load environment variables
load_dotenv()


proxy_host = 'shared-datacenter.geonode.com'
proxy_port = '9008'
proxy_username = os.getenv('PROXY_USERNAME')
proxy_password = os.getenv('PROXY_PASSWORD')

initializing_fail_list = []


SPREADSHEET_APPS_SCRIPT_URL = os.getenv('SPREADSHEET_APPS_SCRIPT_URL')
COLUMN_NAMES = [
    "Auction Date", "County", "Auction Type", "Sold Amount", "Opening Bid",
    "Excess Amount", "Case #", "Parcel ID", "Property Address", "Property City",
    "Property State", "Property Zip", "Assessed Value", "Auction Status",
    "Certificate #", "Sold Date", "Sold To", "Final Judgment Amount",
    "Plaintiff Max Bid", "Lenders Starting Bid Amount"
]

def get_county_prefix(county_website):
    if county_website.startswith(('http://', 'https://')):
        county_website = county_website.split('://', 1)[1]
    if county_website.endswith('.com'):
        county_website = county_website[:-4]
    return county_website.replace('.', '_')


def extract_county_name(county_website):
    county = county_website.split('.')[0]
    return county.capitalize()


def send_auction_data(auction_date, auction_items):
    def format_currency(value):
        if value is None:
            return ""
        return f"${value:.2f}" if isinstance(value, (int, float)) else value

    ordered_items = []
    for item in auction_items:
        ordered_item = {field: item.get(field, "") for field in COLUMN_NAMES}

        # Format currency fields
        currency_fields = ["Sold Amount", "Opening Bid", "Excess Amount", "Assessed Value", "Final Judgment Amount", "Lenders Starting Bid Amount"]
        for field in currency_fields:
            ordered_item[field] = format_currency(ordered_item[field])

        ordered_items.append(ordered_item)

    data = {
        "date": auction_date,
        "items": ordered_items
    }

    try:
        response = requests.post(SPREADSHEET_APPS_SCRIPT_URL, json=data)
        if response.status_code == 200:
            print(f"Successfully sent data for {len(auction_items)} items to Google Sheets.")
            print("Response from server:", response.text)
        else:
            print(f"Failed to send data to Google Sheets. Status code: {response.status_code}")
            print("Response from server:", response.text)
    except Exception as e:
        print(f"An error occurred while sending data to Google Sheets: {str(e)}")


async def initialize_session(page, county_website, formatted_date):
    url = f"https://{county_website}/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate={formatted_date}"
    max_retries = 2
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            await asyncio.wait_for(
                page.goto(url, wait_until="domcontentloaded"),
                timeout=15.0
            )
            content = await page.content()
            if '403 Forbidden' in content:
                raise Exception("403 Forbidden error encountered")
            print("Session initialized")
            return
        except Exception as e:
            retry_count += 1
            print(f"Attempt {retry_count} failed: {str(e)}")
            if retry_count == max_retries:
                initializing_fail_list.append(county_website)
                raise Exception(f"Failed to initialize session after {max_retries} attempts")
            await asyncio.sleep(1)  # Wait for 1 second before retrying



async def fetch_all_pages(page, county_website):
    all_auctions = []
    page_number = 1
    total_pages = None

    while True:
        auction_list = await fetch_auction_list(page, county_website, page_number)
        parsed_auctions = parse_auction_data(auction_list)

        page_info = await fetch_page_info(page, county_website, parsed_auctions['rlist'])
        parsed_page_data = parse_page_data(page_info)

        if total_pages is None:
            total_pages = int(parsed_page_data['pageInfo']['total'])
            logger.info(f"Total pages: {total_pages}")

        if total_pages == 0:
            print("No auctions found for this date.")
            break

        merged_page_data = merge_auction_and_page_data(parsed_auctions, parsed_page_data)
        all_auctions.extend(merged_page_data['auctions'])

        print(f"Processed page {page_number} of {total_pages}")
        page_number += 1

        if page_number > total_pages:
            break

    return {'auctions': all_auctions, 'pageInfo': parsed_page_data['pageInfo']}



async def fetch_auction_list(page, county_website, page_number):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            load_url = f"https://{county_website}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&PageDir=1&doR=0&bypassPage={page_number}"
            response = await page.goto(load_url, wait_until="networkidle")
            
            if response.ok:
                text = await response.text()
                data = json.loads(text.strip())
                print(f"Auction list for page {page_number} fetched successfully")
                return data
            else:
                raise ValueError(f"HTTP error: {response.status}")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                await asyncio.sleep(1)
            else:
                print(f"All {max_retries} attempts failed.")
                raise

async def fetch_page_info(page, county_website, rlist):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            timestamp = int(datetime.now().timestamp() * 1000)
            load_url = f"https://{county_website}/index.cfm?zaction=AUCTION&ZMETHOD=UPDATE&FNC=UPDATE&ref={','.join(rlist)}&tx={timestamp}&_={timestamp - 321}"
            
            response = await page.goto(load_url, wait_until="networkidle")
            
            if response.ok:
                text = await response.text()
                data = json.loads(text.strip())
                print('Page info fetched successfully')
                return data
            else:
                raise ValueError(f"HTTP error: {response.status}")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                await asyncio.sleep(1)
            else:
                print(f"All {max_retries} attempts failed.")
                raise

def preprocess_html(html):
    print('Preprocessing HTML...')
    replacements = {
        '@A': '<div class="', '@B': '</div>', '@C': 'class="', '@D': '<div>', 
        '@E': 'AUCTION', '@F': '</td><td', '@G': '</td></tr>', '@H': '<tr><td ', 
        '@I': 'table', '@J': 'p_back="NextCheck=', '@K': 'style="Display:none"', 
        '@L': '/index.cfm?zaction=auction&zmethod=details&AID='
    }

    for key, value in replacements.items():
        html = html.replace(key, value)
    #print(html)  # For debugging
    return html


def parse_auction_data(data):
    print('Parsing auction data...')
    processed_html = preprocess_html(data['retHTML'])
    #print(processed_html)  # For debugging
    soup = BeautifulSoup(processed_html, 'html.parser')

    auctions = []
    for element in soup.select('.AUCTION_ITEM'):
        item = {}
        address_parts = []
        for row in element.select('tr'):
            label_elem = row.select_one('th')
            value_elem = row.select_one('td')
            
            if label_elem and value_elem:
                label = label_elem.text.strip().rstrip(':')
                if label == 'Parcel ID':
                    value = value_elem.select_one('a').text.strip() if value_elem.select_one('a') else value_elem.text.strip()
                else:
                    value = value_elem.text.strip()

                if label == 'Property Address':
                    address_parts.append(value)
                elif not label:  # This is likely the continuation of the address
                    address_parts.append(value)
                elif label and value:
                    item[label] = value

        # Combine address parts and split into components
        full_address = ' '.join(address_parts)
        address_components = full_address.split(',')
        if len(address_components) == 2:
            item['Property Address'] = address_components[0].strip()
            state_zip = address_components[1].strip().split('-')
            if len(state_zip) == 2:
                item['Property City'] = address_components[0].strip().split()[-1]
                item['Property State'] = state_zip[0].strip()
                item['Property Zip'] = state_zip[1].strip()
        else:
            item['Property Address'] = full_address
            item['Property City'] = ''
            item['Property State'] = ''
            item['Property Zip'] = ''

        auctions.append(item)

    print(f"Parsed {len(auctions)} auctions")
    return {'auctions': auctions, 'rlist': data['rlist'].split(',')}

def parse_page_data(data):
    print('Parsing page data...')
    templates = {
        'A_A': "Auction Starts", 'A_B': "Auction Status", 'PS_A': "NORMAL", 'I_A': "Name on Title (Nickname)",
        'S_A': "AUCTION_ITEM_PUBLIC", 'S_B': "AUCTION_ITEM", 'P_A': "Hidden",
        'E_A': "My Proxy Bid", 'E_B': "My Maximum Bid", 'PB_A': "Place Bid"
    }

    def get_template(i_data, i_field):
        if i_data in ("A", "B"):
            return templates.get(f"{i_field}_{i_data}")
        return False if i_data == "-" else True if i_data == "+" else i_data

    # Check if the expected keys are present in the data
    if 'CC' not in data or 'CM' not in data:
        print("Warning: No auction data found.")
        return {
            'pageInfo': {
                'current': 0,
                'total': 0,
                'winning': {'count': 0, 'max': 0},
                'nextCheck': None
            },
            'resetRequired': {
                'all': False, 'regular': False, 'completed': False, 'winning': False
            },
            'auctions': [],
            'remainingTime': []
        }

    parsed_data = {
        'pageInfo': {
            'current': data.get('CC', 0),
            'total': data.get('CM', 0),
            'winning': {'count': data.get('WC', 0), 'max': data.get('WM', 0)},
            'nextCheck': data.get('NC')
        },
        'resetRequired': {
            'all': data.get('RA', False),
            'regular': data.get('RR', False),
            'completed': data.get('RC', False),
            'winning': data.get('RW', False)
        },
        'auctions': [],
        'remainingTime': []
    }

    if 'ADATA' in data and 'AITEM' in data['ADATA']:
        parsed_data['auctions'] = [{
            'id': item.get('AID'),
            'status': {'message': get_template(item.get('A'), 'A'), 'timestamp': item.get('B')},
            'amount': {'label': item.get('C'), 'value': item.get('D')},
            'soldTo': {'label': item.get('SL'), 'value': item.get('ST')},
            'extraInfo': {
                'proxyBid': get_template(item.get('E'), 'E'),
                'F': item.get('F'),
                'G': item.get('G'),
                'H': item.get('H'),
                'nameOnTitle': get_template(item.get('I'), 'I')
            },
            'bidInfo': {
                'placeBid': get_template(item.get('PB'), 'PB'),
                'showPlaceBid': item.get('SP'),
                'showBidHistory': item.get('SBH')
            },
            'styleInfo': {
                'panelStatus': get_template(item.get('PS'), "PS"),
                'itemType': get_template(item.get('S'), 'S'),
                'priceVisibility': get_template(item.get('P'), 'P')
            },
            'lendersStartingBidAmount': item.get('P')
        } for item in data['ADATA']['AITEM']]

    if 'RTIME' in data and 'RITEM' in data['RTIME']:
        parsed_data['remainingTime'] = [{
            'id': item.get('AID'),
            'timeRemaining': item.get('TREM')
        } for item in data['RTIME']['RITEM']]

    print(f"Parsed page data with {len(parsed_data['auctions'])} auctions")
    return parsed_data



def merge_auction_and_page_data(auctions_data, page_data):
    print('Merging auction data...')
    detailed_auction_map = {auctions_data['rlist'][i]: auction for i, auction in enumerate(
        auctions_data['auctions'])}

    # Save auctions_data and page_data as JSON in results folder
    os.makedirs('results', exist_ok=True)
    with open('results/auctions_data.json', 'w') as f:
        json.dump(auctions_data, f, indent=2)
    with open('results/page_data.json', 'w') as f:
        json.dump(page_data, f, indent=2)
    print('Saved auctions_data.json and page_data.json in results folder')
    merged_data = {
        'pageInfo': page_data['pageInfo'],
        'resetRequired': page_data['resetRequired'],
        'auctions': [{
            **update_auction,
            'details': {
                'auctionType': detailed_auction_map.get(update_auction['id'], {}).get('Auction Type', ''),
                'caseNumber': detailed_auction_map.get(update_auction['id'], {}).get('Case #', ''),
                'finalJudgmentAmount': detailed_auction_map.get(update_auction['id'], {}).get('Final Judgment Amount', ''),
                'parcelId': detailed_auction_map.get(update_auction['id'], {}).get('Parcel ID', ''),
                'assessedValue': detailed_auction_map.get(update_auction['id'], {}).get('Assessed Value', ''),
                'plaintiffMaxBid': detailed_auction_map.get(update_auction['id'], {}).get('Plaintiff Max Bid', ''),
                'propertyAddress': detailed_auction_map.get(update_auction['id'], {}).get('Property Address', ''),
                'propertyCity': detailed_auction_map.get(update_auction['id'], {}).get('Property City', ''),
                'propertyState': detailed_auction_map.get(update_auction['id'], {}).get('Property State', ''),
                'propertyZip': detailed_auction_map.get(update_auction['id'], {}).get('Property Zip', ''),
                'certificateNumber': detailed_auction_map.get(update_auction['id'], {}).get('Certificate #', ''),
                'openingBid': detailed_auction_map.get(update_auction['id'], {}).get('Opening Bid', ''),
                'lendersStartingBidAmount': update_auction.get('lendersStartingBidAmount', '')
            }
        } for update_auction in page_data['auctions']],
        'rlist': auctions_data['rlist']
    }

    print(f"Merged data for {len(merged_data['auctions'])} auctions")
    # Save merged_data as JSON in results folder
    with open('results/merged_data.json', 'w') as f:
        json.dump(merged_data, f, indent=2)
    print('Saved merged_data.json in results folder')
    return merged_data



def clean_and_filter_auction_data(merged_data, auction_date, county_website):
    cleaned_data = []
    county_name = extract_county_name(county_website)
    
    if not merged_data['auctions']:
        print(f"No auctions found for {county_name} on {auction_date}")
        return cleaned_data
    #print(merged_data['auctions'])
    for auction in merged_data['auctions']:
        if auction['soldTo']['value'] == '3rd Party Bidder':
            try:
                cleaned_auction = {column: None for column in COLUMN_NAMES}  # Initialize all columns with None
                
                cleaned_auction.update({
                    'Auction Date': auction_date,
                    'County': county_name,
                    'Auction Type': auction['details'].get('auctionType', ''),
                    'Sold Amount': parse_float(auction['amount']['value']),
                    'Opening Bid': parse_float(auction['details'].get('openingBid', '')),
                    'Case #': auction['details'].get('caseNumber', '').strip(),
                    'Parcel ID': auction['details'].get('parcelId', ''),
                    'Property Address': auction['details'].get('propertyAddress', ''),
                    'Property City': auction['details'].get('propertyCity', ''),
                    'Property State': auction['details'].get('propertyState', ''),
                    'Property Zip': auction['details'].get('propertyZip', ''),
                    'Assessed Value': parse_float(auction['details'].get('assessedValue', '')),
                    'Auction Status': auction['status'].get('message', ''),
                    'Certificate #': auction['details'].get('certificateNumber', ''),
                    'Sold Date': auction['status'].get('timestamp', ''),
                    'Sold To': auction['soldTo'].get('value', ''),
                    'Final Judgment Amount': parse_float(auction['details'].get('finalJudgmentAmount', '')),
                    'Plaintiff Max Bid': parse_float(auction['details'].get('plaintiffMaxBid', '')),
                    'Lenders Starting Bid Amount': parse_float(auction['details'].get('lendersStartingBidAmount', ''))
                })
                
                if cleaned_auction['Auction Type'] == 'FORECLOSURE':
                    if cleaned_auction['Sold Amount'] is not None and cleaned_auction['Final Judgment Amount'] is not None:
                        cleaned_auction['Excess Amount'] = cleaned_auction['Sold Amount'] - cleaned_auction['Final Judgment Amount']
                else:
                    if cleaned_auction['Sold Amount'] is not None and cleaned_auction['Opening Bid'] is not None:
                        cleaned_auction['Excess Amount'] = cleaned_auction['Sold Amount'] - cleaned_auction['Opening Bid']
                
                cleaned_data.append(cleaned_auction)
            except Exception as e:
                print(f"Error processing auction: {e}")

    logger.info(f"Cleaned and filtered data :  {len(cleaned_data)} auctions")

    # Save cleaned_data as JSON in results folder
    os.makedirs('results', exist_ok=True)
    county_prefix = get_county_prefix(county_website)
    with open(f'results/{county_prefix}_cleaned_data.json', 'w') as f:
        json.dump(cleaned_data, f, indent=2)
    print(f'Saved {county_prefix}_cleaned_data.json in results folder')
    return cleaned_data



def parse_float(value):
    try:
        return float(value.replace('$', '').replace(',', '')) if value else None
    except ValueError:
        print(f"Warning: Could not convert '{value}' to float")
        return None


async def save_to_csv(data, filename, county_website):
    print(f'Saving data to CSV: {filename}')
    os.makedirs('results', exist_ok=True)
    county_prefix = get_county_prefix(county_website)
    filepath = os.path.join('results', f"{county_prefix}_{filename}")

    async with aiofiles.open(filepath, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=COLUMN_NAMES)
        await file.write(','.join(COLUMN_NAMES) + '\n')  # Write header
        for row in data:
            csv_row = {field: (str(row.get(field, '')) if row.get(field) is not None else '') for field in COLUMN_NAMES}
            await file.write(','.join(csv_row.values()) + '\n')

    print(f'Data saved to CSV: {filepath}')



async def save_to_json(data, filename, county_website):
    print(f'Saving data to JSON: {filename}')
    os.makedirs('results', exist_ok=True)
    county_prefix = get_county_prefix(county_website)
    filepath = os.path.join('results', f"{county_prefix}_{filename}")

    async with aiofiles.open(filepath, mode='w', encoding='utf-8') as file:
        await file.write(json.dumps(data, indent=2))

    print(f'Data saved to JSON: {filepath}')

#new_scraper.py
def log(message, level='info'):
    if logger:
        if level == 'info':
            logger.info(message)
        elif level == 'error':
            logger.error(message)
        elif level == 'warning':
            logger.warning(message)

async def run_new_scraper(county_website, auction_date=None):
    start_time = time.time()

    if auction_date is None:
        auction_date = datetime.now().date()  # Use today's date
    formatted_date = auction_date.strftime("%m/%d/%Y")

    start_time = datetime.now()
    if logger:
        logger.info(f"Scraper started for website: {county_website}, date: {formatted_date}")
    else:
        print(f"Scraper started for website: {county_website}, date: {formatted_date}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={
                "server": f"http://{proxy_host}:{proxy_port}",
                "username": proxy_username,
                "password": proxy_password
            }
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        page = await context.new_page()

        try:
            if logger:
                logger.info(f'Initializing session for {county_website}...')
            else:
                print(f'Initializing session for {county_website}...')
            await initialize_session(page, county_website, formatted_date)

            if logger:
                logger.info(f'Fetching data from all pages for {county_website}...')
            else:
                print(f'Fetching data from all pages for {county_website}...')
            all_data = await fetch_all_pages(page, county_website)

            if logger:
                logger.info(f'Cleaning and filtering auction data for {county_website}...')
            else:
                print(f'Cleaning and filtering auction data for {county_website}...')
            cleaned_data = clean_and_filter_auction_data(all_data, formatted_date, county_website)

            if cleaned_data:
                if logger:
                    logger.info(f'Saving cleaned auction data to CSV for {county_website}...')
                else:
                    print(f'Saving cleaned auction data to CSV for {county_website}...')
                csv_filename = f"{formatted_date.replace('/', '-')}.csv"
                await save_to_csv(cleaned_data, csv_filename, county_website)

                if logger:
                    logger.info(f'Saving final JSON data for {county_website}...')
                else:
                    print(f'Saving final JSON data for {county_website}...')
                json_filename = f"{formatted_date.replace('/', '-')}_final.json"
                await save_to_json(all_data, json_filename, county_website)

                if logger:
                    logger.info(f'Sending data to Google Sheets for {county_website}...')
                else:
                    print(f'Sending data to Google Sheets for {county_website}...')
                send_auction_data(formatted_date, cleaned_data)
            else:
                if logger:
                    logger.info(f"No auction data found for {county_website} on {formatted_date}. Skipping CSV, JSON, and Google Sheets operations.")
                else:
                    print(f"No auction data found for {county_website} on {formatted_date}. Skipping CSV, JSON, and Google Sheets operations.")

            end_time = datetime.now()
            elapsed_time = (end_time - start_time).total_seconds()
            if logger:
                logger.info(f"Scraper completed successfully for {county_website} at: {end_time.isoformat()}")
                logger.info(f"Total execution time for {county_website}: {elapsed_time:.2f} seconds")
            else:
                print(f"Scraper completed successfully for {county_website} at: {end_time.isoformat()}")
                print(f"Total execution time for {county_website}: {elapsed_time:.2f} seconds")
        except Exception as error:
            end_time = datetime.now()
            elapsed_time = (end_time - start_time).total_seconds()
            if logger:
                logger.error(f"Error in main function for {county_website} after {elapsed_time:.2f} seconds: {str(error)}")
            else:
                print(f"Error in main function for {county_website} after {elapsed_time:.2f} seconds: {str(error)}")
        finally:
            await browser.close()


async def run_all_counties(json_file_path):
    # Load the JSON file
    with open(json_file_path, 'r') as file:
        counties_data = json.load(file)

    # Loop through each county website
    for county_data in counties_data:
        county_website = county_data['website']
        
        print("\n" + "="*50)
        print(f"Starting scraper for: {county_website}")
        print("="*50 + "\n")

        try:
            auction_date = datetime(2024, 9, 11)  # September 18, 2024
            await run_new_scraper(county_website)#, auction_date)
        except Exception as e:
            print(f"Error occurred while scraping {county_website}: {str(e)}")

        print("\n" + "="*50)
        print(f"Finished scraping: {county_website}")
        print("="*50 + "\n")

        # Optional: Add a delay between scraping different websites
        await asyncio.sleep(1)  # 5 seconds delay, adjust as needed

    # Retry failed initializations
    if initializing_fail_list:
        print("\nRetrying failed initializations...")
        retry_list = initializing_fail_list.copy()
        for failed_county in retry_list:
            print(f"Retrying: {failed_county}")
            try:
                await run_new_scraper(failed_county)
                print(f"Successfully scraped on retry: {failed_county}")
            except Exception as e:
                print(f"Failed to scrape on retry: {failed_county}. Error: {str(e)}")

        if initializing_fail_list:
            print("\nCounties that failed after retry:")
            for county in initializing_fail_list:
                print(county)
        else:
            print("\nAll retries successful!")

    # Reset initializing_fail_list regardless of retry results
    initializing_fail_list = []

if __name__ == "__main__":
    json_file_path = 'counties_websites_list.json'
    #county_website = "eagle.realforeclose.com"
    # county_website = "coconino.realtaxdeed.com"
    # asyncio.run(run_new_scraper(county_website))
    if not os.path.exists(json_file_path):
        logger.error(f"Error: The file {json_file_path} does not exist.")
        logger.info("Falling back to default county website...")
        county_website = "manatee.realforeclose.com"
        asyncio.run(run_new_scraper(county_website))
    else:
        asyncio.run(run_all_counties(json_file_path))

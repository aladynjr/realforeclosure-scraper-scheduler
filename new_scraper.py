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

import time 
# Load environment variables
load_dotenv()




proxy_host = 'shared-datacenter.geonode.com'
proxy_port = '9001'
proxy_username = os.getenv('PROXY_USERNAME')
proxy_password = os.getenv('PROXY_PASSWORD')

SPREADSHEET_APPS_SCRIPT_URL = os.getenv('SPREADSHEET_APPS_SCRIPT_URL')

def send_auction_data(auction_date, auction_items):
    ordered_fields = [
        "Auction Date", "County", "Auction Type", "Sold Amount", "Opening Bid", 
        "Excess Amount", "Case #", "Parcel ID", "Property Address", "Property City", 
        "Property State", "Property Zip", "Assessed Value", "Auction Status", 
        "Certificate #", "Sold Date", "Sold To", "Final Judgment Amount",
        "Plaintiff Max Bid"
    ]

    def format_currency(value):
        if value is None:
            return ""
        return f"${value:.2f}" if isinstance(value, (int, float)) else value

    ordered_items = []
    for item in auction_items:
        ordered_item = {field: item.get(field, "") for field in ordered_fields}
        
        # Format currency fields
        for field in ["Sold Amount", "Opening Bid", "Excess Amount", "Assessed Value", "Final Judgment Amount"]:
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
            print("Response from server:")
            print(response.text)
        else:
            print(f"Failed to send data to Google Sheets. Status code: {response.status_code}")
            print("Response from server:")
            print(response.text)
    except Exception as e:
        print(f"An error occurred while sending data to Google Sheets: {str(e)}")
        
async def initialize_session(date=None, max_retries=3):
    for attempt in range(max_retries):
        try:
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

                auction_date = date or datetime.now().strftime("%m/%d/%Y")
                url = f"https://manatee.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate={auction_date}"
                print(f"Navigating to {url}")
                await page.goto(url, wait_until="domcontentloaded")

                cookies = await context.cookies()
                async with aiofiles.open('cookies.json', 'w') as f:
                    await f.write(json.dumps(cookies, indent=2))
                print('Cookies saved to cookies.json')

                await browser.close()
                print('Session initialized successfully')
                return  # Success, exit the function
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                print("All retry attempts exhausted. Session initialization failed.")
                raise  # Re-raise the last exception if all retries fail
            await asyncio.sleep(1)  # Wait for 2 seconds before retrying

async def fetch_all_pages():

    all_auctions = []
    page_number = 1
    total_pages = None
    last_page_info = None

    try:
        while True:
            auction_list = await fetch_auction_list(page_number)
            parsed_auctions = parse_auction_data(auction_list)
            
            page_info = await fetch_page_info(parsed_auctions['rlist'])
            parsed_page_data = parse_page_data(page_info)
            
            if total_pages is None:
                total_pages = int(parsed_page_data['pageInfo']['total'])
                print(f"Total pages: {total_pages}")

            merged_page_data = merge_auction_data(parsed_auctions, parsed_page_data)
            all_auctions.extend(merged_page_data['auctions'])

            last_page_info = parsed_page_data['pageInfo']

            print(f"Processed page {page_number} of {total_pages}")
            page_number += 1

            if page_number > total_pages:
                break

        return {'auctions': all_auctions, 'pageInfo': last_page_info}
    except Exception as error:
        print(f"Error in fetch_all_pages: {str(error)}")
        raise

async def fetch_auction_list(page_number=1, max_retries=3):
    print(f"Fetching auction list for page {page_number}...")
    async with aiofiles.open('cookies.json', 'r') as f:
        cookies_json = await f.read()
    cookies_array = json.loads(cookies_json)
    cookie_string = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies_array if cookie['domain'] == '.realforeclose.com' or cookie['domain'] == 'manatee.realforeclose.com'])

    proxy_url = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
    load_url = f"https://manatee.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&PageDir=1&doR=0&bypassPage={page_number}"

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(load_url, proxy=proxy_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Cookie': cookie_string
                }) as response:
                    content_type = response.headers.get('Content-Type', '')
                    text = await response.text()
                    
                    print(f"Response status: {response.status}")
                    
                    # Trim the response text before parsing JSON
                    trimmed_text = text.strip()
                    data = json.loads(trimmed_text)
                    print(f"Auction list for page {page_number} fetched successfully")
                    return data
        except (json.JSONDecodeError, ValueError, aiohttp.ClientError) as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                print("Max retries reached. Unable to fetch auction list.")
                if 'html' in content_type.lower():
                    print("Received HTML response. Attempting to extract data...")
                    soup = BeautifulSoup(text, 'html.parser')
                    error_message = soup.find('div', class_='error-message')
                    if error_message:
                        print(f"Error message found: {error_message.text.strip()}")
                raise ValueError(f"Unable to parse response as JSON. Content type: {content_type}")
            else:
                print(f"Retrying in 2 seconds...")
                await asyncio.sleep(1)


async def fetch_page_info(rlist, max_retries=3):
    print('Fetching page info...')
    async with aiofiles.open('cookies.json', 'r') as f:
        cookies_json = await f.read()
    cookies_array = json.loads(cookies_json)
    cookie_string = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies_array if cookie['domain'] == '.realforeclose.com' or cookie['domain'] == 'manatee.realforeclose.com'])

    proxy_url = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"

    timestamp = int(datetime.now().timestamp() * 1000)
    load_url = f"https://manatee.realforeclose.com/index.cfm?zaction=AUCTION&ZMETHOD=UPDATE&FNC=UPDATE&ref={','.join(rlist)}&tx={timestamp}&_={timestamp - 321}"

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(load_url, proxy=proxy_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Cookie': cookie_string,
                    'referer': 'https://manatee.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=09/16/2024',
                    'x-requested-with': 'XMLHttpRequest'
                }) as response:
                    content_type = response.headers.get('Content-Type', '')
                    text = await response.text()
                    
                    print(f"Response status: {response.status}")
                    
                    # Trim the response text before parsing JSON
                    trimmed_text = text.strip()
                    data = json.loads(trimmed_text)
                    print('Page info fetched successfully')
                    return data
        except (json.JSONDecodeError, ValueError, aiohttp.ClientError) as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                print("Max retries reached. Unable to fetch page info.")
                raise
            else:
                print(f"Retrying in 2 seconds...")
                await asyncio.sleep(1)


def preprocess_html(html):
    print('Preprocessing HTML...')
    replacements = {
        '@A': '<div class="',
        '@B': '</div>',
        '@C': 'class="',
        '@D': '<div>',
        '@E': 'AUCTION',
        '@F': '</td><td',
        '@G': '</td></tr>',
        '@H': '<tr><td ',
        '@I': 'table',
        '@J': 'p_back="NextCheck=',
        '@K': 'style="Display:none"',
        '@L': '/index.cfm?zaction=auction&zmethod=details&AID='
    }

    for key, value in replacements.items():
        html = html.replace(key, value)
    return html

def parse_auction_data(data):
    print('Parsing auction data...')
    processed_html = preprocess_html(data['retHTML'])
    soup = BeautifulSoup(processed_html, 'html.parser')

    auctions = []
    for element in soup.select('.AUCTION_ITEM'):
        item = {}
        address_parts = []
        for row in element.select('tr'):
            label = row.select_one('th').text.strip().rstrip(':')
            value_elem = row.select_one('td')
            if label == 'Parcel ID':
                value = value_elem.select_one('a').text.strip()
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

    parsed_data = {
        'pageInfo': {
            'current': data['CC'], 'total': data['CM'],
            'winning': {'count': data['WC'], 'max': data['WM']},
            'nextCheck': data['NC']
        },
        'resetRequired': {
            'all': data['RA'], 'regular': data['RR'], 'completed': data['RC'], 'winning': data['RW']
        },
        'auctions': [{
            'id': item['AID'],
            'status': {'message': get_template(item['A'], 'A'), 'timestamp': item['B']},
            'amount': {'label': item['C'], 'value': item['D']},
            'soldTo': {'label': item['SL'], 'value': item['ST']},
            'extraInfo': {
                'proxyBid': get_template(item['E'], 'E'), 'F': item['F'], 'G': item['G'], 'H': item['H'],
                'nameOnTitle': get_template(item['I'], 'I')
            },
            'bidInfo': {
                'placeBid': get_template(item['PB'], 'PB'),
                'showPlaceBid': item['SP'], 'showBidHistory': item['SBH']
            },
            'styleInfo': {
                'panelStatus': get_template(item['PS'], "PS"),
                'itemType': get_template(item['S'], 'S'),
                'priceVisibility': get_template(item['P'], 'P')
            }
        } for item in data['ADATA']['AITEM']],
        'remainingTime': [{
            'id': item['AID'], 'timeRemaining': item['TREM']
        } for item in data['RTIME']['RITEM']]
    }

    print(f"Parsed page data with {len(parsed_data['auctions'])} auctions")
    return parsed_data

def merge_auction_data(detailed_data, update_data):
    print('Merging auction data...')
    detailed_auction_map = {detailed_data['rlist'][i]: auction for i, auction in enumerate(detailed_data['auctions'])}

    # Save detailed_data and update_data as JSON in results folder
    os.makedirs('results', exist_ok=True)
    with open('results/detailed_data.json', 'w') as f:
        json.dump(detailed_data, f, indent=2)
    with open('results/update_data.json', 'w') as f:
        json.dump(update_data, f, indent=2)
    print('Saved detailed_data.json and update_data.json in results folder')

    merged_data = {
        'pageInfo': update_data['pageInfo'],
        'resetRequired': update_data['resetRequired'],
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
                'openingBid': detailed_auction_map.get(update_auction['id'], {}).get('Opening Bid', '')
            }
        } for update_auction in update_data['auctions']],
        'rlist': detailed_data['rlist']
    }

    print(f"Merged data for {len(merged_data['auctions'])} auctions")
    # Save merged_data as JSON in results folder
    with open('results/merged_data.json', 'w') as f:
        json.dump(merged_data, f, indent=2)
    print('Saved merged_data.json in results folder')
    return merged_data



def clean_and_filter_auction_data(merged_data, auction_date):
    print('Cleaning and filtering auction data...')
    cleaned_data = []
    for auction in merged_data['auctions']:
        if auction['soldTo']['value'] == '3rd Party Bidder':
            try:
                cleaned_auction = {
                    'Auction Date': auction_date,
                    'County': 'Manatee',
                    'Auction Type': auction['details']['auctionType'],
                    'Sold Amount': parse_float(auction['amount']['value']),
                    'Opening Bid': parse_float(auction['details']['openingBid']),
                    'Case #': auction['details']['caseNumber'].strip(),
                    'Parcel ID': auction['details']['parcelId'],
                    'Property Address': auction['details']['propertyAddress'],
                    'Property City': auction['details'].get('propertyCity', ''),
                    'Property State': auction['details'].get('propertyState', ''),
                    'Property Zip': auction['details'].get('propertyZip', ''),
                    'Assessed Value': parse_float(auction['details']['assessedValue']),
                    'Auction Status': auction['status']['message'],
                    'Certificate #': auction['details']['certificateNumber'],
                    'Sold Date': auction['status']['timestamp'],
                    'Sold To': auction['soldTo']['value'],
                    'Final Judgment Amount': parse_float(auction['details']['finalJudgmentAmount'])
                }
                if cleaned_auction['Auction Type'] == 'FORECLOSURE':
                    if cleaned_auction['Sold Amount'] is not None and cleaned_auction['Final Judgment Amount'] is not None:
                        cleaned_auction['Excess Amount'] = cleaned_auction['Sold Amount'] - cleaned_auction['Final Judgment Amount']
                    else:
                        cleaned_auction['Excess Amount'] = None
                else:
                    if cleaned_auction['Sold Amount'] is not None and cleaned_auction['Opening Bid'] is not None:
                        cleaned_auction['Excess Amount'] = cleaned_auction['Sold Amount'] - cleaned_auction['Opening Bid']
                    else:
                        cleaned_auction['Excess Amount'] = None
                cleaned_data.append(cleaned_auction)
            except KeyError as e:
                print(f"Warning: Missing key in auction data: {e}")
            except Exception as e:
                print(f"Error processing auction: {e}")
    
    print(f"Cleaned and filtered data for {len(cleaned_data)} auctions")
    
    # Save cleaned_data as JSON in results folder
    os.makedirs('results', exist_ok=True)
    with open('results/cleaned_data.json', 'w') as f:
        json.dump(cleaned_data, f, indent=2)
    print('Saved cleaned_data.json in results folder')
    return cleaned_data

def parse_float(value):
    try:
        return float(value.replace('$', '').replace(',', '')) if value else None
    except ValueError:
        print(f"Warning: Could not convert '{value}' to float")
        return None

# ... [rest of the script remains the same] ...

async def save_to_csv(data, filename):
    print(f'Saving data to CSV: {filename}')
    os.makedirs('results', exist_ok=True)
    filepath = os.path.join('results', filename)
    
    fieldnames = [
        'Auction Date', 'County', 'Auction Type', 'Sold Amount', 'Opening Bid', 
        'Excess Amount', 'Case #', 'Parcel ID', 'Property Address', 'Property City',
        'Property State', 'Property Zip', 'Assessed Value', 'Auction Status',
        'Certificate #', 'Sold Date', 'Sold To', 'Final Judgment Amount'
    ]
    
    async with aiofiles.open(filepath, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        await file.write(','.join(fieldnames) + '\n')  # Write header
        for row in data:
            await file.write(','.join(str(row.get(field, '')) for field in fieldnames) + '\n')
    
    print(f'Data saved to CSV: {filepath}')

async def save_to_json(data, filename):
    print(f'Saving data to JSON: {filename}')
    os.makedirs('results', exist_ok=True)
    filepath = os.path.join('results', filename)
    
    async with aiofiles.open(filepath, mode='w', encoding='utf-8') as file:
        await file.write(json.dumps(data, indent=2))
    
    print(f'Data saved to JSON: {filepath}')

async def run_new_scraper(auction_date=None):
    start_time = time.time()

    if auction_date is None:
        auction_date = datetime(2024, 9, 16)
    formatted_date = auction_date.strftime("%m/%d/%Y")


    start_time = datetime.now()
    print(f"Scraper started at: {start_time.isoformat()}")

    try:
        print('Initializing session...')

        await initialize_session(formatted_date)
        
        print('Fetching data from all pages...')
        all_data = await fetch_all_pages()
        
        print('Cleaning and filtering auction data...')
        cleaned_data = clean_and_filter_auction_data(all_data, date)
        
        print('Saving cleaned auction data to CSV...')
        csv_filename = f"{date.replace('/', '-')}.csv"
        await save_to_csv(cleaned_data, csv_filename)

        print('Saving final JSON data...')
        json_filename = f"{date.replace('/', '-')}_final.json"
        await save_to_json(all_data, json_filename)

        print('Sending data to Google Sheets...')
        send_auction_data(date, cleaned_data)

        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        print(f"Scraper completed successfully at: {end_time.isoformat()}")
        print(f"Total execution time: {elapsed_time:.2f} seconds")
    except Exception as error:
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        print(f"Error in main function after {elapsed_time:.2f} seconds:", str(error))


if __name__ == "__main__":
    asyncio.run(run_new_scraper())
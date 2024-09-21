import requests
import os
import json
import logging
from dotenv import load_dotenv
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from urllib.parse import urlparse

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Suppress only the single InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def make_requests_with_proxy():
    logging.info("Starting the request process...")
    
    url = 'https://manatee.realforeclose.com/index.cfm'
    
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://manatee.realforeclose.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://manatee.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=09/18/2024',
        'sec-ch-ua': '"Chromium";v="129", "Not=A?Brand";v="8"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest'
    }

    site_ids = [72, 69, 77, 48, 82, 106, 100, 97, 93, 58, 78, 105, 13, 73, 29, 17, 107, 3, 35, 30, 67, 68, 2, 32, 19, 18, 53, 51, 81, 55, 95, 96, 41, 56, 38, 64, 25, 54, 101, 102, 37, 8, 7, 44, 49, 42, 79, 26, 71, 15, 27, 92, 16, 65, 90, 21, 22, 31, 34, 99, 14, 50, 23, 24, 20, 28, 57, 74, 66, 45, 52, 11, 70, 103, 84, 43, 10, 6, 108, 76, 109, 86]

    proxy_host = 'shared-datacenter.geonode.com'
    proxy_port = '9008'
    proxy_username = os.getenv('PROXY_USERNAME')
    proxy_password = os.getenv('PROXY_PASSWORD')

    logging.info(f"Using proxy: {proxy_host}:{proxy_port}")

    proxy_url = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"

    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }

    results = []
    total_requests = len(site_ids)

    session = requests.Session()
    session.proxies.update(proxies)

    for index, vendor_id in enumerate(site_ids, start=1):
        logging.info(f"Processing request {index}/{total_requests} for vendor ID: {vendor_id}")
        
        data = {
            'ZACTION': 'AJAX',
            'ZMETHOD': 'LOGIN',
            'func': 'SWITCH',
            'VENDOR': str(vendor_id)
        }

        for attempt in range(3):  # 3 retry attempts without delay
            try:
                logging.info(f"Sending request to {url}... (Attempt {attempt + 1})")
                response = session.post(
                    url,
                    headers=headers,
                    data=data,
                    timeout=30,
                    verify=False
                )
                response.raise_for_status()
                logging.info(f"Request successful. Status code: {response.status_code}")
                
                # Print the full response
                print(f"\nFull response for vendor ID {vendor_id}:")
                print(response.text.strip())
                print("\n" + "-"*50 + "\n")  # Separator for readability
                
                results.append({
                    'vendor_id': vendor_id,
                    'status_code': response.status_code,
                    'response': response.text
                })
                break  # If successful, break out of the retry loop
            except requests.exceptions.RequestException as e:
                logging.error(f"Error occurred: {str(e)}")
                if attempt == 2:  # If this was the last attempt
                    results.append({
                        'vendor_id': vendor_id,
                        'error': str(e)
                    })

    logging.info("All requests completed.")
    return results


def save_to_json(data):
    counties_websites_list = [
        {
            "website": "manatee.realforeclose.com"
        }
    ]
    
    for item in data:
        if 'response' in item:
            try:
                # Parse the JSON response
                response_data = json.loads(item['response'])
                full_url = response_data.get('URL', '')
                if full_url:
                    # Extract just the domain name
                    parsed_url = urlparse(full_url)
                    website = parsed_url.netloc
                else:
                    website = 'URL not found'
            except json.JSONDecodeError:
                logging.error(f"Failed to parse JSON for vendor ID {item['vendor_id']}")
                website = 'Failed to parse response'
            
            counties_websites_list.append({
                "website": website
            })
    
    with open('counties_websites_list.json', 'w') as f:
        json.dump(counties_websites_list, f, indent=2)
    
    logging.info("Saved counties websites list to counties_websites_list.json")
    logging.info(f"Extracted {len(counties_websites_list)} website URLs")

    # Print the first few entries for verification
    print("\nFirst few entries of the extracted data:")
    for entry in counties_websites_list[:6]:  # Increased to 6 to show the added entry plus 5 others
        print(f"Website: {entry['website']}")
if __name__ == "__main__":
    logging.info("Starting the script...")
    responses = make_requests_with_proxy()
    logging.info("\nSummary of results:")
    for response in responses:
        if 'error' in response:
            logging.error(f"Vendor ID {response['vendor_id']}: Error - {response['error']}")
        else:
            logging.info(f"Vendor ID {response['vendor_id']}: Status {response['status_code']}, Response preview: {response['response'][:100]}...")
    
    save_to_json(responses)
    logging.info("Script execution completed.")
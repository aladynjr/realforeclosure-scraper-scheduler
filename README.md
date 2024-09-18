# Manatee County Real Estate Auction Scraper

This project contains a web scraper for Manatee County real estate auctions, along with a scheduler to run the scraper daily at 6 PM EST.

## Features

- Scrapes auction data from the Manatee County real estate auction website
- Saves data in both JSON and CSV formats
- Sends scraped data to a Google Spreadsheet
- Scheduled to run daily at 6 PM EST
- Comprehensive logging for monitoring and troubleshooting

## Requirements

- Python 3.7+
- Required Python packages:
  - playwright
  - beautifulsoup4
  - requests
  - python-dotenv
  - schedule
  - pytz

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/your-username/manatee-auction-scraper.git
   cd manatee-auction-scraper
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Set up your environment variables in a `.env` file:
   ```
   PROXY_USERNAME=your_proxy_username
   PROXY_PASSWORD=your_proxy_password
   ```

4. Install Playwright browsers:
   ```
   playwright install
   ```

## Usage

- To run the scraper once for testing:
  ```
  python scraper.py
  ```

- To start the scheduled scraper:
  ```
  python main.py
  ```

The scheduler will run the scraper daily at 6 PM EST. Logs will be written to `scraper_scheduler.log` and displayed in the console.

## Project Structure

- `scraper.py`: Contains the main scraping logic
- `main.py`: Handles scheduling and execution of the scraper
- `requirements.txt`: Lists all Python package dependencies
- `scraper_scheduler.log`: Log file for the scheduler and scraper operations

## Note

Ensure that your system clock is accurate, as the scheduler relies on the system time to determine when to run the scraper.
# Manatee County Real Estate Auction Scraper

This project contains a web scraper for Manatee County real estate auctions, along with a scheduler to run the scraper daily at 6 PM EST and integrate the data with a Google Spreadsheet. It also includes a simple web-based log viewer for easy monitoring.

## Features

- Scrapes auction data from the Manatee County real estate auction website
- Filters and processes only auction items sold to 3rd party bidders
- Saves data in both JSON and CSV formats with consistent field ordering
- Calculates and includes Excess Amount for each auction item
- Sends scraped data to a Google Spreadsheet, maintaining field order
- Scheduled to run daily at 6 PM EST
- Comprehensive logging for monitoring and troubleshooting
- Web-based log viewer for easy access to logs

## Requirements

- Python 3.7+
- Required Python packages:
  - playwright
  - beautifulsoup4
  - requests
  - python-dotenv
  - schedule
  - pytz
  - flask
- Google account for Spreadsheet integration

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

5. Set up Google Spreadsheet integration (see section below)

## Usage

- To run the scraper once for testing:
  ```
  python scraper.py
  ```

- To start the scheduled scraper and log viewer:
  ```
  python main.py
  ```

The scheduler will run the scraper daily at 6 PM EST. Logs will be written to `scraper_scheduler.log` and can be viewed through the web interface.

## Project Structure

- `scraper.py`: Contains the main scraping logic and data processing
- `main.py`: Handles scheduling and execution of the scraper
- `log_viewer.py`: Flask application for viewing logs
- `requirements.txt`: Lists all Python package dependencies
- `scraper_scheduler.log`: Log file for the scheduler and scraper operations
- `SpreadsheetAppsScriptdoPost.gs`: Google Apps Script for Spreadsheet integration

## Log Viewer

The project now includes a web-based log viewer for easy monitoring of the scraper's operation. 

### Features:
- Displays logs in reverse chronological order (most recent first)
- Automatically refreshes every 60 seconds
- Filters out unrelated Flask and server logs
- Accessible via web browser

### Usage:
1. The log viewer starts automatically when you run `main.py`
2. Access the logs by navigating to `http://your_ip:5000` in a web browser
3. The page will show only relevant logs related to the scraper's operation
4. The page refreshes automatically every 60 seconds to show the latest logs

Note: Ensure that port 5000 is open on your VPS firewall to access the log viewer.


## Data Processing

The scraper processes the auction data with the following key features:

1. **3rd Party Bidder Filter**: The scraper only collects and processes auction items that have been sold to 3rd party bidders.

2. **Consistent Field Ordering**: The data is processed to ensure consistent field ordering across JSON, CSV, and Google Spreadsheet outputs. The fields are ordered as follows:

   Auction Date, County, Auction Type, Sold Amount, Opening Bid, Excess Amount, Case #, Parcel ID, Property Address, Property City, Property State, Property Zip, Assessed Value, Auction Status, Final Judgment Amount, Plaintiff Max Bid, Sold Date, Sold To

3. **Excess Amount Calculation**: The Excess Amount is calculated as the difference between the Sold Amount and the Opening Bid, with a minimum value of 0.

## Google Spreadsheet Integration

This project uses Google Apps Script to automatically update a Google Spreadsheet with the scraped data. The integration now maintains the specified field order and includes the Excess Amount calculation.

### Google Apps Script Setup

1. Create a new Google Spreadsheet or open an existing one where you want to store the auction data.

2. In the spreadsheet, go to Extensions > Apps Script.

3. In the Apps Script editor, replace the default code with the contents of `SpreadsheetAppsScriptdoPost.gs`:

```javascript
function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(data.date);
  
  if (!sheet) {
    sheet = SpreadsheetApp.getActiveSpreadsheet().insertSheet(data.date);
  } else {
    // Clear existing content if sheet already exists
    sheet.clear();
  }
  
  if (data.items.length > 0) {
    // Add headers
    var headers = Object.keys(data.items[0]);
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    
    // Add data
    var rows = data.items.map(function(item) {
      return headers.map(function(header) {
        return item[header] || '';
      });
    });
    
    sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
  }
  
  var response = {
    status: "success",
    message: data.items.length + " items added to the spreadsheet for date " + data.date + ". Any existing data for this date has been overwritten."
  };
  
  return ContentService.createTextOutput(JSON.stringify(response)).setMimeType(ContentService.MimeType.JSON);
}
```

4. Save the project (File > Save).

### Deploying as a Web App

1. Click on "Deploy" > "New deployment".

2. For "Select type", choose "Web app".

3. Set the following options:
   - Execute as: "Me"
   - Who has access: "Anyone"

4. Click "Deploy" and authorize the app when prompted.

5. After deployment, you'll receive a URL. Copy this URL and update the `WEBAPP_URL` variable in your `scraper.py` file with this new URL.

### How It Works

- The script creates a new sheet for each auction date or clears an existing sheet if one already exists for that date.
- It then populates the sheet with the scraped auction data, with each row representing an auction item.
- The data is now ordered according to the specified field order, including the newly added Excess Amount.
- The script only processes items sold to 3rd party bidders, as filtered by the Python scraper.
- The script responds with a success message indicating the number of items added.

Note: Ensure that you have the necessary permissions to create and modify Google Spreadsheets in your Google account.

## Example Scraped Data

Below is an example of the JSON data structure produced by the scraper:

```json
{
  "auction_date": "09/18/2024",
  "total_items": 1,
  "auction_items": [
    {
      "Auction Date": "09/18/2024",
      "County": "Manatee",
      "Auction Type": "FORECLOSURE",
      "Sold Amount": "$288,300.00",
      "Opening Bid": "$197,300.00",
      "Excess Amount": "$91,000.00",
      "Case #": "412023CA004038CAAXMA",
      "Parcel ID": "740902859",
      "Property Address": "8243 47TH STREET CIR E",
      "Property City": "PALMETTO",
      "Property State": "FL",
      "Property Zip": "34221",
      "Assessed Value": "$393,733.00",
      "Auction Status": "Auction Sold",
      "Final Judgment Amount": "$425,000.00",
      "Plaintiff Max Bid": "Hidden",
      "Sold Date": "09/18/2024 11:04 AM ET",
      "Sold To": "3rd Party Bidder"
    }
  ]
}
```

This example shows the structure of the scraped data, including the auction date, total number of items, and details for each auction item.

To view the complete example dataset, please visit:
[https://api.npoint.io/255205498e8050f4dab5](https://api.npoint.io/255205498e8050f4dab5)

The actual output will contain more items and may include additional fields depending on the available data for each auction.

## Note

Ensure that your system clock is accurate, as the scheduler relies on the system time to determine when to run the scraper. Also, be aware that the number of items scraped may vary significantly from day to day, as it depends on the number of auctions sold to 3rd party bidders on any given date.



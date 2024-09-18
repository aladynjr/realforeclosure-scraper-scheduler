# Manatee County Real Estate Auction Scraper

This project contains a web scraper for Manatee County real estate auctions, along with a scheduler to run the scraper daily at 6 PM EST and integrate the data with a Google Spreadsheet.

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
- `SpreadsheetAppsScriptdoPost.gs`: Google Apps Script for Spreadsheet integration

## Google Spreadsheet Integration

This project uses Google Apps Script to automatically update a Google Spreadsheet with the scraped data. Here's how to set it up:

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
- The script responds with a success message indicating the number of items added.

Note: Ensure that you have the necessary permissions to create and modify Google Spreadsheets in your Google account.

## Example Scraped Data

Below is a truncated example of the JSON data structure produced by the scraper:

```json
{
  "auction_date": "09/18/2024",
  "total_items": 10,
  "auction_items": [
    {
      "Auction Status": "Auction Sold",
      "Sold Date": "09/18/2024 10:15 AM",
      "Sold Amount": "$277,002.00",
      "Sold To": "THIRD PARTY",
      "Case #": "2023 CA 001819",
      "Parcel ID": "3738310303",
      "Property Address": "7611 41ST CT E, SARASOTA, FL 34243",
      "Auction Type": "Mortgage Foreclosure",
      "Attorney's Phone": "813-229-0900",
      "Opening Bid": "$197,300.00",
      "Assessed Value": "$218,395.00",
      "Property City": "SARASOTA",
      "Property State": "FL",
      "Property Zip": "34243",
      "Auction Date": "09/18/2024",
      "County": "Manatee"
    }
    // ... more items
  ]
}
```

This example shows the structure of the scraped data, including the auction date, total number of items, and details for each auction item.

To view the complete example dataset, please visit:
[https://api.npoint.io/255205498e8050f4dab5](https://api.npoint.io/255205498e8050f4dab5)

The actual output will contain more items and may include additional fields depending on the available data for each auction.

## Note

Ensure that your system clock is accurate, as the scheduler relies on the system time to determine when to run the scraper.
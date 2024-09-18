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
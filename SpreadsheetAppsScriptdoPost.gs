function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(data.date);
  
  if (!sheet) {
    sheet = SpreadsheetApp.getActiveSpreadsheet().insertSheet(data.date);
    var headers = Object.keys(data.items[0]);
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
  
  var existingData = sheet.getDataRange().getValues();
  var headers = existingData[0];
  var caseNumberIndex = headers.indexOf("Case #");
  
  if (caseNumberIndex === -1) {
    throw new Error("Column 'Case #' not found in the sheet.");
  }
  
  var existingCaseNumbers = existingData.slice(1).map(row => row[caseNumberIndex]);
  var newRows = [];
  var updatedRows = 0;
  
  data.items.forEach(function(item) {
    var rowIndex = existingCaseNumbers.indexOf(item["Case #"]);
    if (rowIndex === -1) {
      // New row, add it
      newRows.push(headers.map(header => item[header] || ''));
    } else {
      // Existing row, update it
      var rowToUpdate = rowIndex + 2; // +2 because of 0-indexing and header row
      sheet.getRange(rowToUpdate, 1, 1, headers.length).setValues([headers.map(header => item[header] || '')]);
      updatedRows++;
    }
  });
  
  // Append new rows if any
  if (newRows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, newRows.length, headers.length).setValues(newRows);
  }
  
  var response = {
    status: "success",
    message: newRows.length + " new items added and " + updatedRows + " items updated in the spreadsheet for date " + data.date + "."
  };
  
  return ContentService.createTextOutput(JSON.stringify(response)).setMimeType(ContentService.MimeType.JSON);
}
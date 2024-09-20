function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  var allSheet = getOrCreateSheet(spreadsheet, 'all');
  
  var headers = Object.keys(data.items[0]);
  ensureHeaders(allSheet, headers);
  
  var caseNumberIndex = headers.indexOf("Case #");
  if (caseNumberIndex === -1) {
    throw new Error("Column 'Case #' not found in the headers.");
  }
  
  var result = processSheet(allSheet, data.items, headers, caseNumberIndex);
  
  var response = {
    status: "success",
    message: `${result.newRows} new items added and ${result.updatedRows} items updated in the 'all' sheet.`
  };
  
  return ContentService.createTextOutput(JSON.stringify(response)).setMimeType(ContentService.MimeType.JSON);
}

function getOrCreateSheet(spreadsheet, sheetName) {
  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }
  return sheet;
}

function ensureHeaders(sheet, headers) {
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
}

function processSheet(sheet, items, headers, caseNumberIndex) {
  var existingData = sheet.getDataRange().getValues();
  var existingCaseNumbers = existingData.slice(1).map(row => row[caseNumberIndex]);
  var newRows = [];
  var updatedRows = 0;
  
  items.forEach(function(item) {
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
  
  return { newRows: newRows.length, updatedRows: updatedRows };
}
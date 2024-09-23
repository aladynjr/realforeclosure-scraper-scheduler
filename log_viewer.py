# log_viewer.py

from flask import Flask, render_template_string
import os
import re

app = Flask(__name__)

LOG_FILE = 'scraper.log'

def is_relevant_log(log_line):
    # Patterns to exclude
    exclude_patterns = [
        r'\d+\.\d+\.\d+\.\d+ - - \[.*?\] ".*?" \d+ -',  # Flask access logs
        r'Running on .*',  # Flask startup messages
        r'Press CTRL\+C to quit',  # Flask quit message
        r'Restarting with.*',  # Flask restart messages
        r'\* Debugger is active!',  # Flask debug messages
        r'\* Debugger PIN:.*',  # Flask debugger PIN
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - (?:INFO|ERROR) - .*? - - \[.*?\] ".*?" (?:HTTPStatus\..*?|-) -',  # Generic pattern for HTTP request logs
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - (?:INFO|WARNING) - .*?(?:development server|Do not use it in a production deployment).*',  # Development server warnings
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - ERROR - .*? - - \[.*?\] code \d+, message .*'  # Error messages related to bad requests
    ]
    
    return not any(re.search(pattern, log_line) for pattern in exclude_patterns)
@app.route('/')
def view_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            logs = f.readlines()
        
        # Filter logs
        logs = [log for log in logs if is_relevant_log(log)]
        
        logs.reverse()  # Show most recent logs first
    else:
        logs = ["No logs found."]
    
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Scraper Logs</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            h1 { color: #333; }
            pre { background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; }
            .starting { color: #0000FF; font-weight: bold; }
            .initializing { color: #FFA500; }
            .fetching { color: #800080; }
            .cleaning { color: #008080; }
            .completed { color: #008000; font-weight: bold; background-color: #90EE90; }
            .error { color: #FF0000; font-weight: bold; background-color: #FFA07A; }
            .sleeping { color: #808080; }
        </style>
    </head>
    <body>
        <h1>Scraper Logs</h1>
        <pre>{{ logs | safe }}</pre>
        <script>
            setTimeout(function(){ location.reload(); }, 60000);  // Refresh every 60 seconds
        </script>
    </body>
    </html>
    """
    
    # Process logs to add HTML tags for highlighting
    processed_logs = []
    for log in logs:
        if "Initializing session" in log or "Sleeping for" in log:
            processed_logs.append("\n")
       # log = re.sub(r'Scraper started for website: (\S+)', r'Scraper started for website: <a href="http://\1" target="_blank">\1</a>', log)
        log = re.sub(r'(\S+\.realforeclose\.com)', r'<a href="http://\1" target="_blank">\1</a>', log)
        log = re.sub(r'(\S+\.realtaxdeed\.com)', r'<a href="http://\1" target="_blank">\1</a>', log)
        log = log.replace("Scraper started", '<span class="starting">Scraper started</span>')
    #    log = log.replace("Initializing session", '<span class="initializing">Initializing session</span>')
        log = log.replace("Total auctions found", '<span class="fetching">Total auctions found</span>')
     #   log = log.replace("Cleaning and filtering", '<span class="cleaning">Cleaning and filtering</span>')
        log = log.replace("completed successfully", '<span class="completed">completed successfully</span>')
        log = log.replace("Error", '<span class="error">Error</span>')
        log = log.replace("Sleeping", '<span class="sleeping">Sleeping</span>')
        processed_logs.append(log)
    
    return render_template_string(html_template, logs=''.join(processed_logs))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
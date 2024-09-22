#main.py 
# 
import asyncio
import time
from datetime import datetime
import pytz
import logging
from new_scraper import run_all_counties
from log_viewer import app as flask_app
import threading

from logger import get_logger

logger = get_logger()


def job():
    est_time = datetime.now(pytz.timezone('US/Eastern'))
    logger.info(f"Starting scraper job at {est_time} EST (TESTING RUN)")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            json_file_path = 'counties_websites_list.json'
            asyncio.run(run_all_counties(json_file_path))
            logger.info("Scraper job completed successfully (TESTING RUN)")
            return  # Exit the function if successful
        except Exception as e:
            retry_count += 1
            logger.error(f"Error occurred during scraper job (attempt {retry_count}/{max_retries}): {str(e)} (TESTING RUN)", exc_info=True)
            if retry_count < max_retries:
                logger.info(f"Retrying in 5 minutes... (TESTING RUN)")
                time.sleep(300)  # Wait for 5 minutes before retrying
    
    logger.error("FAILED ALL 3 RETRIES (TESTING RUN)")

def run_flask():
    flask_app.run(host='0.0.0.0', port=5000)

def get_logger():
    return logger

if __name__ == "__main__":
    try:
        # Start Flask app in a separate thread
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Run the job once
        logger.info("Starting testing run of the scraper")
        job()
    except KeyboardInterrupt:
        logger.info("Scraper stopped by user (TESTING RUN)")
        print("Scraper stopped by user (TESTING RUN)")
    except Exception as e:
        logger.critical(f"Unexpected error occurred: {str(e)} (TESTING RUN)", exc_info=True)
        print(f"Unexpected error occurred: {str(e)} (TESTING RUN)")
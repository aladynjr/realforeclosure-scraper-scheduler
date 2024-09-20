import asyncio
import schedule
import time
from datetime import datetime, timedelta
import pytz
import logging
from scraper import run_scraper
from new_scraper import run_new_scraper
from log_viewer import app as flask_app
import threading

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def job():
    est_time = datetime.now(pytz.timezone('US/Eastern'))
    logger.info(f"Starting scraper job at {est_time} EST")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            today = datetime.now().date()
            asyncio.run(run_new_scraper(auction_date=today))
            logger.info("Scraper job completed successfully")
            return  # Exit the function if successful
        except Exception as e:
            retry_count += 1
            logger.error(f"Error occurred during scraper job (attempt {retry_count}/{max_retries}): {str(e)}", exc_info=True)
            if retry_count < max_retries:
                logger.info(f"Retrying in 5 minutes...")
                time.sleep(300)  # Wait for 5 minutes before retrying
    
    logger.error("FAILED ALL 3 RETRIES")

def run_schedule():
    est = pytz.timezone('US/Eastern')
    
    def schedule_next_run():
        now = datetime.now(est)
        next_run = now.replace(hour=18, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        return next_run
    
    def time_until_next_run():
        return (schedule_next_run() - datetime.now(est)).total_seconds()

    logger.info("Starting the scraper scheduler")
    
    while True:
        try:
            # Schedule the next run
            next_run = schedule_next_run()
            logger.info(f"Next scraper run scheduled for: {next_run} EST")
            
            # Sleep until the next run time
            sleep_seconds = time_until_next_run()
            logger.info(f"Sleeping for {sleep_seconds / 3600:.2f} hours until next run")
            
            try:
                time.sleep(sleep_seconds)
            except KeyboardInterrupt:
                logger.info("Sleep interrupted by user")
                raise  # re-raise to be caught by outer try-except
            
            # Run the job
            job()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {str(e)}", exc_info=True)
            # Optional: add a short sleep to prevent tight error loops
            time.sleep(60)

def run_flask():
    flask_app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    try:
        # Start Flask app in a separate thread
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Run the main scheduler
        run_schedule()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.critical(f"Unexpected error occurred: {str(e)}", exc_info=True)
import logging

def setup_logger():
    logger = logging.getLogger('scraper')
    logger.setLevel(logging.INFO)
    
    # Create file handler
    file_handler = logging.FileHandler('scraper.log')
    file_handler.setLevel(logging.INFO)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create and configure the logger
logger = setup_logger()

def get_logger():
    return logger
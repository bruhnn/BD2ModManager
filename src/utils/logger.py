import logging

def setup_logging(log_file_path):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s @ %(levelname)s - %(funcName)s : %(message)s')

    # File handler
    file_handler = logging.FileHandler(log_file_path, mode="w", encoding="UTF-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)  
    
    logger.addHandler(console_handler)

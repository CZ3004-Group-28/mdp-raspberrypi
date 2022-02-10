import logging


def prepare_logger():

    log_format = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    if not logger.hasHandlers():
        # console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)

        # file handler
        file_handler = logging.FileHandler('logfile.txt')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_format)

        # add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger

import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s]:[%(asctime)s] - [%(filename)s] - [%(funcName)s] -> %(message)s",
    datefmt="%d/%m/%Y %I:%M:%S %p"
)

def create_logger():
    return logging.getLogger(__name__)
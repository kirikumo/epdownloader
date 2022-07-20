import logging
import os


class CustomFormatter(logging.Formatter):
    format = '[%(asctime)s: %(levelname)s] [%(filename)s:%(lineno)d] %(message)s'

    FORMATS = {
        logging.DEBUG: format,
        logging.INFO: format,
        logging.WARNING: format,
        logging.ERROR: format,
        logging.FATAL: format,
        logging.CRITICAL: format
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logger(filePath=None, level=logging.INFO):
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    logFormat = CustomFormatter()
    # sh = logging.StreamHandler()
    # sh.setFormatter(logFormat)
    # logger.addHandler(sh)

    if filePath is not None:
        os.makedirs(os.path.dirname(filePath), exist_ok=True)
        fh = logging.FileHandler(filePath)
        fh.setFormatter(logFormat)
        logger.addHandler(fh)

    return logger

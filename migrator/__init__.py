import logging
import traceback
import sys

# Initialize a logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)

# Set the log format to include only the message
handler = logging.StreamHandler()
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def exception_logging(exctype, value, tb):
    """
    Log exception by using the root logger.

    Parameters
    ----------
    exctype : type
    value : NameError
    tb : traceback
    """
    write_val = {
        "exception_type": str(exctype),
        "message": str(traceback.format_tb(tb, 10)),
    }
    logger.error(write_val)


sys.excepthook = exception_logging

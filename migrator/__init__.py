import logging
import traceback
import sys

# Get a named logger (e.g., based on the module name)
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)

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

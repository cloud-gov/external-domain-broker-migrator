import logging
import time

from migrator.db import check_connections


def main():
    logging.basicConfig(level=logging.DEBUG)
    check_connections()
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()

import logging
import time

import schedule

from migrator.extensions import config
from migrator.db import check_connections, session_handler
from migrator.migration import migrate_ready_instances
from migrator.cf import get_cf_client


def run_and_report():
    with session_handler() as session:
        results = migrate_ready_instances(session, get_cf_client(config))
    # todo: report results
    print(results)


def main():
    logging.basicConfig(level=logging.DEBUG)
    check_connections()
    schedule.every().tuesday.at(config.MIGRATION_TIME).do(run_and_report)
    schedule.every().wednesday.at(config.MIGRATION_TIME).do(run_and_report)
    schedule.every().thursday.at(config.MIGRATION_TIME).do(run_and_report)
    while True:
        time.sleep(1)
        schedule.run_pending()


if __name__ == "__main__":
    main()

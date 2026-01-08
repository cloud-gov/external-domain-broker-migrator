import argparse
import schedule
import sys
import time

from migrator.extensions import config
from migrator.db import check_connections, session_handler
from migrator.migration import migrate_ready_instances, migrate_single_instance
from migrator.cf import get_cf_client
from migrator.smtp import send_report_email


def run_and_report():
    with session_handler() as session:
        results = migrate_ready_instances(session, get_cf_client(config))
    send_report_email(results)


def parse_args(args):
    parser = argparse.ArgumentParser()
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--cron",
        action="store_true",
        help="Run daemon, migrating all ready instances on a scheduled",
    )
    action_group.add_argument(
        "--instance", help="run once against the specified instance"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip DNS checks for single-instance migration",
    )
    parser.add_argument(
        "--skip-site-dns-check",
        action="store_true",
        help="Skip DNS check of site domain record for single-instance migration",
    )
    return parser.parse_args(args)


def main():
    args = parse_args(sys.argv[1:])
    check_connections()
    if args.cron:
        schedule.every().tuesday.at(config.MIGRATION_TIME).do(run_and_report)
        schedule.every().wednesday.at(config.MIGRATION_TIME).do(run_and_report)
        schedule.every().thursday.at(config.MIGRATION_TIME).do(run_and_report)
        while True:
            time.sleep(1)
            schedule.run_pending()
    elif args.instance:
        with session_handler() as session:
            migrate_single_instance(
                args.instance,
                session,
                get_cf_client(config),
                skip_dns_check=args.force,
                skip_site_dns_check=args.skip_site_dns_check,
            )


if __name__ == "__main__":
    main()

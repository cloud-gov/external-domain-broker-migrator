import sys
from flagger import queries, aws


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("Dry run: not making any actual changes")
    for domain in queries.find_domains():
        aws.create_semaphore(domain, dry_run)


if __name__ == "__main__":
    main()

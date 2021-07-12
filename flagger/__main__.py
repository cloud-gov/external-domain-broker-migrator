import sys
from flagger import queries, aws


def main():
    args = sys.argv
    dry_run = False
    while len(args) > 1:
        arg = args.pop()
        if arg == "--dry-run":
            dry_run = True
        else:
            print(f"Unknown option: {arg}\nUsage: python3 -m flagger [--dry-run]")
            exit(1)
    if dry_run:
        print("Dry run: not making any actual changes")
    domains = queries.find_domains()
    print(f"{len(domains)} domain(s) found")
    for domain in domains:
        aws.create_semaphore(domain, dry_run)
    domain_cdns = queries.find_aliases()
    for domain_cdn in domain_cdns():
        aws.create_cdn_alias(*domain_cdn, dry_run)


if __name__ == "__main__":
    main()

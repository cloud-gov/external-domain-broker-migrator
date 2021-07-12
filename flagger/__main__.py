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
    with session_handler() as session:
        domains = queries.find_domains(session)
    print(f"{len(domains)} domain(s) found")
    for domain in domains:
        aws.create_semaphore(domain, dry_run)
    with session_handler() as session:
        domain_cdns = queries.find_cdn_aliases(session)
    for domain_cdn in domain_cdns():
        aws.create_cdn_alias(*domain_cdn, dry_run)
    with session_handler() as session:
        domain_albs = queries.find_albs(session)
    for domain_alb in domain_albs():
        aws.create_alb_alias(*domain_alb, dry_run)


if __name__ == "__main__":
    main()

import boto3

route53 = boto3.client("route53")

def create_semaphore(domain, dry_run=False):
    print(f"Creating TXT record for: {domain}")
    if dry_run: return
    # TODO: implement Route53 TXT record creation here

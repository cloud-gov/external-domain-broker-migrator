from migrator.extensions import route53, config


def create_semaphore(domain, dry_run=False):
    resource_name = f"_acme-challenge.{domain}.{config.DNS_ROOT_DOMAIN}"
    print(f"Creating semaphore TXT record '{config.SEMAPHORE}' for {resource_name}")
    if dry_run:
        return
    route53.change_resource_record_sets(
        HostedZoneId=config.ROUTE53_ZONE_ID,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": resource_name,
                        "Type": "TXT",
                        "TTL": 60,
                        "ResourceRecords": [{"Value": f'"{config.SEMAPHORE}"'}],
                    },
                }
            ]
        },
    )


def create_cdn_alias(internal_domain, cloudfront_domain, dry_run):
    print(f"Creating ALIAS '{internal_domain}' => {cloudfront_domain}")
    if dry_run:
        return
    alias_record = f"{internal_domain}.{config.DNS_ROOT_DOMAIN}"
    route53_response = route53.change_resource_record_sets(
        ChangeBatch={
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Type": "A",
                        "Name": alias_record,
                        "AliasTarget": {
                            "DNSName": cloudfront_domain,
                            "HostedZoneId": config.CLOUDFRONT_HOSTED_ZONE_ID,
                            "EvaluateTargetHealth": False,
                        },
                    },
                },
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Type": "AAAA",
                        "Name": alias_record,
                        "AliasTarget": {
                            "DNSName": cloudfront_domain,
                            "HostedZoneId": config.CLOUDFRONT_HOSTED_ZONE_ID,
                            "EvaluateTargetHealth": False,
                        },
                    },
                },
            ]
        },
        HostedZoneId=config.ROUTE53_ZONE_ID,
    )


def create_domain_alias(internal_domain, alb_domain, dry_run):
    print(f"Creating ALIAS '{internal_domain}' => {alb_domain}")
    if dry_run:
        return
    alias_record = f"{internal_domain}.{config.DNS_ROOT_DOMAIN}"
    route53_response = route53.change_resource_record_sets(
        ChangeBatch={
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Type": "A",
                        "Name": alias_record,
                        "AliasTarget": {
                            "DNSName": alb_domain,
                            "HostedZoneId": config.ALB_HOSTED_ZONE_ID,
                            "EvaluateTargetHealth": False,
                        },
                    },
                },
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Type": "AAAA",
                        "Name": alias_record,
                        "AliasTarget": {
                            "DNSName": alb_domain,
                            "HostedZoneId": config.ALB_HOSTED_ZONE_ID,
                            "EvaluateTargetHealth": False,
                        },
                    },
                },
            ]
        },
        HostedZoneId=config.ROUTE53_ZONE_ID,
    )

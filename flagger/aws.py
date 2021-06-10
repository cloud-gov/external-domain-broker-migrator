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
                        "ResourceRecords": [{"Value": config.SEMAPHORE}],
                    },
                }
            ]
        },
    )

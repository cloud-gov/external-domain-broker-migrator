# external-domain-broker-migrator

Migrate [cdn-broker](https://github.com/cloud-gov/cdn-broker) instances to the [external-domain-broker](https://github.com/cloud-gov/external-domain-broker)


## Migration Plan

*this is the _plan_ for how we'll do this. Much of this is not yet developed, so may change*
The external-domain-broker requires customers to set up three ALIAS/CNAME records 
pointing to predictable DNS names under our control. Two are for the hostname of the actual
site (e.g. `www.example.gov`), one as an A record, one as an AAAA record. The other is a 
TXT record which we use for validation to retrieve Let's Encrypt certificates on their
behalf. This is why we cannot simply migrate behind the scenes, all at once.
The migrator contains a script to pre-create our side of these DNS records, and will
pre-create the TXT records with a semaphore value. This way, regardless of whether a 
customer uses a CNAME (which is publicly discoverable) or an ALIAS (which is internal
to their DNS), we'll be able to detect their changes easily.
The migrator works by periodically checking all the active instances in the 
cdn-broker's database. It queries DNS for the _acme-challenge TXT record to
see if the customer has configured it to point to the intermediate record 
used by the external-domain broker. 
Once the DNS is correctly configured, the migrator check if the service instance's 
certificate expires within 32 days (to try to avoid migrating while a renewal is in
progress), and if not begins the migration of the instance. 
1. Enable the external-domain-service migration plan in the service instance's
   space. This plan is a special plan used only for this purpose.
2. Create an instance of the migration plan in the space.
3. Query CloudFront and IAM to get the settings of the existing service instance
4. Transform the information from CloudFront, IAM, and the cdn-broker database 
   to create a CdnServiceInstance in the external-domain-broker's database
5. Create an Operation record in the external-domain-broker's database to update
   the new service instance from a migration plan to the domain-with-cdn plan
6. Call update-service on the new instance so CAPI knows about the plan change.
   the external-domain-broker treats this as a no-op, since the migrator already
   changed the plan
7. Call purge-service on the old service instance, so CAPI knows it's gone, but 
   the cdn-broker doesn't delete the cloudfront distribution
8. Mark the instance as inactive in the cdn-broker database so the cdn-broker 
   doesn't try to renew its certificate
9. Disable the external-domain-service migration plan in the space
10. Rename the new service instance to the name of the old service instance
11. (maybe) email the account manager to inform them the migration has completed

## Contributing

See [CONTRIBUTING](CONTRIBUTING.md) for additional information.

## Public domain

This project is in the worldwide [public domain](LICENSE.md). As stated in [CONTRIBUTING](CONTRIBUTING.md):

> This project is in the public domain within the United States, and copyright and related rights in the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/).
>
> All contributions to this project will be released under the CC0 dedication. By submitting a pull request, you are agreeing to comply with this waiver of copyright interest.

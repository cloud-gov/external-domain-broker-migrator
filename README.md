# external-domain-broker-migrator

Migrate [cdn-broker](https://github.com/cloud-gov/cdn-broker) and
[custom-domain](https://github.com/cloud-gov/cf-domain-broker-alb) instances to the [external-domain-broker](https://github.com/cloud-gov/external-domain-broker)

## Migrating a single instance via a one-off task

```shell
python3 -m migrator --instance <old-domain-or-cdn-service-guid>
```

## Migration Plan

The external-domain-broker requires customers to set up three ALIAS/CNAME records
pointing to predictable DNS names under our control.

Two of the records are for the hostname of the actual
site (e.g. `www.example.gov`), one as an `A` record, one as an `AAAA` record. The other is a
`TXT` record which we use for validation to retrieve Let's Encrypt certificates on their
behalf. This is why we cannot simply migrate behind the scenes, all at once.

This migrator contains a script to pre-create our side of these DNS records, and will
pre-create the TXT records with a semaphore value. This way, regardless of whether a
customer uses a CNAME (which is publicly discoverable) or an ALIAS (which is internal
to their DNS), we'll be able to detect their changes easily.

The migrator works by periodically checking all the active instances in the
`cdn-broker`'s database. It queries DNS for the _acme-challenge TXT record to
see if the customer has configured it to point to the intermediate record
used by the external-domain broker.

The migrator goes through the following steps to migrate a service:

1. Enable the external-domain-service migration plan in the service instance's
   space. This plan is a special plan used only for this purpose.
2. Create an instance of the migration plan in the space.
3. Query CloudFront and IAM to get the settings of the existing service instance
4. Transform the information from CloudFront, IAM, and the cdn-broker database
   to create a CdnServiceInstance in the external-domain-broker's database
5. Call update-service on the new instance so CAPI knows about the plan change.
6. Call purge-service on the old service instance, so CAPI knows it's gone, but
   the cdn-broker doesn't delete the cloudfront distribution
7. Mark the instance as inactive in the cdn-broker database so the cdn-broker
   doesn't try to renew its certificate
8. Disable the external-domain-service migration plan in the space
9. Rename the new service instance to the name of the old service instance
10. (maybe) email the account manager to inform them the migration has completed

## Testing

Tests are split into two categories: unit and integration.

### Unit tests

Unit tests can be run without external services - this should help speed up testing and enable
tests being run in e.g, github actions.

To run unit tests:

1. create a virtual environment
2. install the dev dependencies into your environment
3. set `ENV` to `unit`
4. run pytest, specifying the unit directory

```bash
python3 -m venv venv
venv/bin/python3 -m pip install -r ./pip-tools/dev-requirements.txt
ENV=unit venv/bin/python3 -m pytest tests/unit
```

### Integration tests

Integration tests require out-of-process services, making them more realistic but harder to run.
Specifically, they include `pebble` as a stand-in for Lets Encrypt and they use `postgresql` rather than `sqlite`.

Integration tests require a working docker (or equivalent) environment, and can be run with `./dev tests`

## Contributing

See [CONTRIBUTING](CONTRIBUTING.md) for additional information.

## Public domain

This project is in the worldwide [public domain](LICENSE.md). As stated in [CONTRIBUTING](CONTRIBUTING.md):

> This project is in the public domain within the United States, and copyright and related rights in the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/).
>
> All contributions to this project will be released under the CC0 dedication. By submitting a pull request, you are agreeing to comply with this waiver of copyright interest.

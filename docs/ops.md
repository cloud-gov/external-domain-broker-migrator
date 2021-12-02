# Operational Docs

## Cleaning up a failed migration

Use these instructions if a migration fails, and you want to retry it
(e.g. you found and fixed the issue that caused it to fail).
*note: if the migrator called `update` on the migration instance, this could get much more complicated, and fixing forward might be better*

1. Get the guid of the migration service instance:
   ```
   $ cf service <instance-name> --guid
   ```
2. Purge the new service instance:
   ```
   $ cf purge-service-instance <migration instance name>
   ```
3. If the migrator called `update` on the migration instance, you'll need to 
   mark the instance as deactivated:
   ```
   $ cf connect-to-service external-domain-broker external-domain-broker-psql
   > update service_instance set deactivated_at = now() where id = '<guid from step 1>';
   ```
4. Get the guid of the original insance:
   ```
   $ cf service <instance-name> --guid
   ```
5. Mark the original instance as provisioned. For cdn instances:
   ```
   $ cf connect-to-service cdn-broker rds-cdn-broker
   > update routes set state = 'provisioned' where instance_id = '<guid>';
   ```
   for alb instances, hop on a jumpbox, get the connection details from BOSH,
   and connect to the database. Then run:
   ```
   > update routes set state = 'provisioned' where guid = '<guid>';
   ```
6. If you want to retry the migration immediately:
   ```
   $ cf run-task external-domain-broker-migrator -c 'python3 -m migrator --instance <guid from step 4>'
   ```


import time

from cloudfoundry_client.client import CloudFoundryClient
from cloudfoundry_client.errors import InvalidStatusCode

from migrator import logger
from migrator.extensions import config


def get_cf_client(config):
    # "why is this a function, and the rest of these are static?"
    # good question. The __init__ on this immediately probes the
    # api endpoint, which means we need to stub it for testing.
    # and having to add that stub to every test that _might_
    # `import extensions` would be bonkers. As a function, we should
    # only need to stub when we're actually thinking about CF
    logger.debug("getting cf client")
    client = CloudFoundryClient(config.CF_API_ENDPOINT)
    client.init_with_user_credentials(config.CF_USERNAME, config.CF_PASSWORD)
    return client


def enable_plan_for_org(plan_id: str, org_id: str, client: CloudFoundryClient):
    logger.debug("enabling plan for %s", org_id)
    orgs = [{"guid": org_id}]
    try:
        response = client.v3.service_plans.apply_visibility_to_extra_orgs(plan_id, orgs)
    except InvalidStatusCode as e:
        if e.body["error_code"] != "CF-ServicePlanVisibilityAlreadyExists":
            raise e


def disable_plan_for_org(plan_id: str, org_id: str, client: CloudFoundryClient):
    logger.debug("disabling plan visibility")
    return client.v3.service_plans.remove_org_from_service_plan_visibility(
        plan_id, org_id
    )


def get_space_id_for_service_instance_id(instance_id: str, client: CloudFoundryClient):
    logger.debug("getting space_id for instance %s", instance_id)
    response = client.v3.service_instances.get(instance_id)
    return response["relationships"]["space"]["data"]["guid"]


def get_org_id_for_space_id(space_id: str, client: CloudFoundryClient):
    logger.debug("getting org_id for space %s", space_id)
    response = client.v3.spaces.get(space_id)
    return response["relationships"]["organization"]["data"]["guid"]


def get_all_space_ids_for_org(org_id: str, client: CloudFoundryClient):
    logger.debug("getting space_ids for org %s", org_id)
    spaces = client.v3.spaces.list(organization_guids=[org_id])
    return [space["guid"] for space in spaces]


def create_bare_migrator_service_instance_in_space(
    space_id: str,
    plan_id: str,
    instance_name: str,
    domains: list[str],
    client: CloudFoundryClient,
):
    logger.debug("creating service instance for space %s", space_id)

    create_response = client.v3.service_instances.create(
        space_guid=space_id,
        service_plan_guid=plan_id,
        name=instance_name,
        parameters=dict(domains=domains),
    )
    job_link = create_response["links"]["job"]["href"]
    job_id = job_link.split("/")[-1]
    return job_id


def wait_for_job_complete(job_id: str, client: CloudFoundryClient):
    logger.debug("polling job status for %s", job_id)

    response = client.v3.jobs.wait_for_job_completion(
        job_id,
        step=config.SERVICE_CHANGE_POLL_TIME_SECONDS,
        timeout=(
            config.SERVICE_CHANGE_RETRY_COUNT * config.SERVICE_CHANGE_POLL_TIME_SECONDS
        ),
    )

    if response["state"] != "COMPLETE":
        raise Exception(f"Job failed {response}")
    return response


def wait_for_service_instance_create(job_id, client: CloudFoundryClient):
    response = wait_for_job_complete(job_id, client)
    service_instance_link = response["links"]["service_instances"]["href"]
    service_instance_id = service_instance_link.split("/")[-1]
    return service_instance_id


def update_existing_cdn_domain_service_instance(
    instance_id: str,
    params: dict,
    client: CloudFoundryClient,
    *,
    new_instance_name=None,
    new_plan_guid=None,
):
    logger.debug("updating service instance %s", instance_id)
    update_response = client.v3.service_instances.update(
        instance_id,
        parameters=params,
        name=new_instance_name,
        service_plan=new_plan_guid,
    )
    job_link = update_response["links"]["job"]["href"]
    job_id = job_link.split("/")[-1]
    return job_id


def purge_service_instance(instance_id: str, client: CloudFoundryClient):
    logger.debug("purging service instance %s", instance_id)
    client.v3.service_instances.remove(instance_id)

    deleted = False
    retry_count = 0

    while not deleted and retry_count < config.SERVICE_CHANGE_RETRY_COUNT:
        try:
            client.v3.service_instances.get(instance_id)
        except InvalidStatusCode as e:
            if e.body["error_code"] == "CF-ResourceNotFound":
                deleted = True
        retry_count += 1
        time.sleep(config.SERVICE_CHANGE_POLL_TIME_SECONDS)

    if not deleted:
        raise RuntimeError(
            f"Could not verify deletion of service instance {instance_id}"
        )


def get_instance_data(instance_id: str, client: CloudFoundryClient):
    return client.v3.service_instances.get(instance_id)

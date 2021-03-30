from cloudfoundry_client.client import CloudFoundryClient


def get_cf_client(config):
    # "why is this a function, and the rest of these are static?"
    # good question. The __init__ on this immediately probes the
    # api endpoint, which means we need to stub it for testing.
    # and having to add that stub to every test that _might_
    # `import extensions` would be bonkers. As a function, we should
    # only need to stub when we're actually thinking about CF
    client = CloudFoundryClient(config.CF_API_ENDPOINT)
    client.init_with_user_credentials(config.CF_USERNAME, config.CF_PASSWORD)
    return client


def enable_plan_for_org(plan_id, org_id, client):
    response = client.v2.service_plan_visibilities.create(plan_id, org_id)
    return response["metadata"]["guid"]


# Takes in service plan visibility GUID
def disable_plan_for_org(spv_id, client):
    return client.v2.service_plan_visibilities.remove(spv_id)


def get_space_id_for_service_instance_id(instance_id, client):
    response = client.v2.service_instances.get(instance_id)
    return response["entity"]["space_guid"]


def get_org_id_for_space_id(space_id, client):
    response = client.v3.spaces.get(space_id)
    return response["relationships"]["organization"]["data"]["guid"]

def get_service_plan_visibility_id_for_org_id(org_id, client):
    response = client.v3.organizations.get(org_id)
    return response["relationships"][""]

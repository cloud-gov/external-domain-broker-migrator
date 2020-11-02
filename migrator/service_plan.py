def enable_plan_for_org(plan_id, org_id, client):
    return client.v2.service_plan_visibilities.create(plan_id, org_id)


def disable_plan_for_org(plan_id, org_id, client):
    pass

from datetime import datetime, timezone

import pytest

from migrator.extensions import route53 as real_route53
from tests.lib.fake_aws import FakeAWS


class FakeRoute53(FakeAWS):
    def expect_create_ALIAS_and_return_change_id(
        self, domain, target, target_hosted_zone_id="Z2FDTNDATAQYW2"
    ) -> str:
        change_id = f"{domain} ID"
        self.stubber.add_response(
            "change_resource_record_sets",
            self._change_info(change_id, "PENDING"),
            {
                "ChangeBatch": {
                    "Changes": [
                        {
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "Name": domain,
                                "Type": "A",
                                "AliasTarget": {
                                    "DNSName": target,
                                    "HostedZoneId": target_hosted_zone_id,
                                    "EvaluateTargetHealth": False,
                                },
                            },
                        },
                        {
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "Name": domain,
                                "Type": "AAAA",
                                "AliasTarget": {
                                    "DNSName": target,
                                    "HostedZoneId": target_hosted_zone_id,
                                    "EvaluateTargetHealth": False,
                                },
                            },
                        },
                    ]
                },
                "HostedZoneId": "FAKEZONEID",
            },
        )
        return change_id

    def expect_create_TXT_and_return_change_id(
        self, domain, semaphore, target_hosted_zone_id="Z2FDTNDATAQYW2"
    ) -> str:
        change_id = f"{domain} ID"
        self.stubber.add_response(
            "change_resource_record_sets",
            self._change_info(change_id, "PENDING"),
            {
                "ChangeBatch": {
                    "Changes": [
                        {
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "Name": domain,
                                "Type": "TXT",
                                "TTL": 60,
                                "ResourceRecords": [{"Value": semaphore}],
                            },
                        }
                    ]
                },
                "HostedZoneId": "FAKEZONEID",
            },
        )
        return change_id

    def expect_wait_for_change_insync(self, change_id: str):
        self.stubber.add_response(
            "get_change", self._change_info(change_id, "PENDING"), {"Id": change_id}
        )
        self.stubber.add_response(
            "get_change", self._change_info(change_id, "INSYNC"), {"Id": change_id}
        )

    def _change_info(self, change_id: str, status: str = "PENDING"):
        now = datetime.now(timezone.utc)
        return {
            "ChangeInfo": {
                "Id": change_id,
                "Status": status,
                "SubmittedAt": now,
                "Comment": "Some comment",
            }
        }


@pytest.fixture(autouse=True)
def route53():
    with FakeRoute53.stubbing(real_route53) as route53_stubber:
        yield route53_stubber

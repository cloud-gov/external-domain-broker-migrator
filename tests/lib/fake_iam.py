import datetime
import pytest
from migrator.extensions import iam_commercial as real_iam_commercial
from migrator.extensions import iam_govcloud as real_iam_govcloud

from tests.lib.fake_aws import FakeAWS


class FakeIAM(FakeAWS):
    def expect_get_server_certificate(
        self,
        certificate_name,
        certificate_id,
        certificate_path: str = None,
        certificate_body: str = None,
        certificate_chain: str = None,
        upload_date: datetime = None,
        expiration_date: datetime = None,
    ):
        certificate_path = certificate_path or "/cloudfront/something"
        certificate_body = certificate_body or "certificate-body"
        certificate_chain = certificate_chain or "certificate-chain"
        upload_date = upload_date or datetime.datetime.now()
        expiration_date = expiration_date or (
            datetime.datetime.now() + datetime.timedelta(days=1)
        )
        request = {"ServerCertificateName": certificate_name}
        response = {
            "ServerCertificate": {
                "ServerCertificateMetadata": {
                    "Path": certificate_path,
                    "ServerCertificateName": certificate_name,
                    "ServerCertificateId": certificate_id,
                    "Arn": f"aws:::{certificate_path}/{certificate_name}",
                    "UploadDate": upload_date,
                    "Expiration": expiration_date,
                },
                "CertificateBody": certificate_body,
                "CertificateChain": certificate_chain,
            }
        }
        self.stubber.add_response("get_server_certificate", response, request)

    def expect_list_server_certificates(
        self,
        target_certificate_name,
        target_certificate_id,
        target_certificate_path: str = None,
        target_certificate_upload_date: datetime = None,
        target_certificate_expiration_date: datetime = None,
        extra_certs: int = 3,
        marker_in: str = None,
        is_truncated: bool = False,
        path_prefix: str = None,
    ):
        target_certificate_upload_date = (
            target_certificate_upload_date or datetime.datetime.now()
        )
        target_certificate_expiration_date = target_certificate_expiration_date or (
            datetime.datetime.now() + datetime.timedelta(days=1)
        )
        certs = []
        certs.append(
            {
                "Path": target_certificate_path,
                "ServerCertificateName": target_certificate_name,
                "ServerCertificateId": target_certificate_id,
                "Arn": f"aws:::{target_certificate_path}/{target_certificate_name}",
                "UploadDate": target_certificate_upload_date,
                "Expiration": target_certificate_expiration_date,
            }
        )
        for i in range(extra_certs):
            certs.append(
                {
                    "Path": target_certificate_path,
                    "ServerCertificateName": "extra-cert-{i}",
                    "ServerCertificateId": "extra-cert-id-{i}",
                    "Arn": f"aws:::{target_certificate_path}/extra-cert-{i}",
                    "UploadDate": target_certificate_upload_date,
                    "Expiration": target_certificate_expiration_date,
                }
            )
        request = {}
        if path_prefix is not None:
            request["PathPrefix"] = path_prefix
        if marker_in is not None:
            request["Marker"] = marker_in
        else:
            marker_in = 0
        response = {
            "ServerCertificateMetadataList": certs,
            "IsTruncated": is_truncated,
            "Marker": str(int(marker_in) + 1),
        }
        self.stubber.add_response("list_server_certificates", response, request)


@pytest.fixture
def iam_commercial():
    with FakeIAM.stubbing(real_iam_commercial) as iam_stubber:
        yield iam_stubber


@pytest.fixture
def iam_govcloud():
    with FakeIAM.stubbing(real_iam_govcloud) as iam_stubber:
        yield iam_stubber

from flagger import aws


def test_create_semaphore_txt_record(route53):
    # No assertion needed in this test; fake route53 will throw an exception on failure
    route53.expect_create_TXT_and_return_change_id(
        "_acme-challenge.example.com.domains.cloud.test", "cloud-gov-migration-ready"
    )
    aws.create_semaphore("example.com")

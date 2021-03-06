import re

import pytest
import requests_mock

from tests.lib.database import clean_db
from tests.lib.dns import dns
from tests.lib.fake_cf import fake_cf_client
from tests.lib.fake_cloudfront import cloudfront
from tests.lib.fake_iam import iam_commercial
from tests.lib.fake_route53 import route53


def pytest_configure(config):
    config.addinivalue_line("markers", "focus: Only run this test.")


def pytest_collection_modifyitems(items, config):
    """
    Focus on tests marked focus, if any.  Run all
    otherwise.
    """

    selected_items = []
    deselected_items = []

    focused = False

    for item in items:
        if item.get_closest_marker("focus"):
            focused = True
            selected_items.append(item)
        else:
            deselected_items.append(item)

    if focused:
        print("\nOnly running @pytest.mark.focus tests")
        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items


@pytest.fixture
def fake_requests():
    with requests_mock.Mocker(real_http=False) as m:
        # let dns stuff come through
        fake_dns_matcher = re.compile("http://localhost:8055/.*")
        m.register_uri(requests_mock.ANY, fake_dns_matcher, real_http=True)
        yield m

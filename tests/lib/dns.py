from dataclasses import dataclass

import pytest
import requests


class DNS:
    """
    I interact with the pebble-challtestsrv process to add and clear DNS
    entries.  See
    https://github.com/letsencrypt/pebble/blob/master/cmd/pebble-challtestsrv/README.md
    for the API.
    """

    @dataclass
    class Entry:
        record_type: str
        host: str
        base: str
        target: str = ""
        value: str = ""

        def __post_init__(self):
            if self.record_type == "txt":
                requests.post(
                    self.base + "/set-txt",
                    json={"host": self.host, "value": self.value},
                ).raise_for_status()
            elif self.record_type == "cname":
                requests.post(
                    self.base + "/set-cname",
                    json={"host": self.host, "target": self.target},
                ).raise_for_status()
            else:
                raise Exception(f"unknown record type: {self.record_type}")

        def clear(self):
            requests.post(
                self.base + f"/clear-{self.record_type}", json={"host": self.host}
            ).raise_for_status()

        def print_history(self):
            print(f"    {len(self.history())} requests for {self.host}")

        def history(self):
            response = requests.post(
                self.base + "/dns-request-history", json={"host": self.host}
            )
            response.raise_for_status()
            items = response.json()
            return items

        def __str__(self):
            return f"{self.host} {self.record_type.upper()} with value {self.value}{self.target}"

    def __init__(self):
        self.base = "http://localhost:8055"
        self.entries = {}

    def add_cname(self, host, target=None):

        if not target:
            target = f"{host}.domains.cloud.test."
        self.entries[host] = self.Entry(
            record_type="cname", host=host, target=target, base=self.base
        )

    def print_info(self):
        print("DNS information:")
        print("  Request History:")

        for _, entry in self.entries.items():
            # Unfortunately, "host" is required, so we have to loop through
            # entries. This also means we won't see any requests for entries
            # we haven't created.
            entry.print_history()

        print("  Local entries:")

        for entry in self.entries:
            print(f"    {entry}")

    def clear_all(self):
        for _, entry in self.entries.items():
            # Unfortunately, the pebble-challtestsrv doesn't expose a
            # "clear-all" endpoint.
            entry.clear()
        self.entries = {}


@pytest.fixture(scope="function")
def dns():
    dns = DNS()
    yield dns
    dns.print_info()
    dns.clear_all()

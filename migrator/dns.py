import dns.resolver

from migrator.extensions import config

(_nameserver, _port) = config.DNS_VERIFICATION_SERVER.split(":")
_root_dns = config.DNS_ROOT_DOMAIN
_resolver = dns.resolver.Resolver(configure=False)
_resolver.nameservers = [_nameserver]
_resolver.port = int(_port)


def get_cname(domain: str) -> str:
    try:
        answers = _resolver.resolve(domain, "CNAME")
        print(answers)

        return answers[0].target.to_text(omit_final_dot=True)

    except dns.resolver.NXDOMAIN:
        return ""

    except dns.resolver.NoAnswer:
        return ""


def get_txt(domain: str) -> list:
    try:
        answers = _resolver.resolve(domain, "TXT")
        results = []
        for answer in answers:
            results.append(answer.to_text().strip('"'))
        return results

    except dns.resolver.NXDOMAIN:
        return []

    except dns.resolver.NoAnswer:
        return []


def acme_challenge_cname_target(domain: str) -> str:
    return f"_acme-challenge.{domain}.{_root_dns}"


def acme_challenge_cname_name(domain: str) -> str:
    return f"_acme-challenge.{domain}"


def has_expected_cname(domain: str) -> bool:
    return get_cname(acme_challenge_cname_name(domain)) == acme_challenge_cname_target(
        domain
    )


def has_expected_semaphore(domain: str) -> bool:
    return config.SEMAPHORE in get_txt(acme_challenge_cname_name(domain))

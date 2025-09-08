import dns.resolver

from migrator import logger
from migrator.extensions import config

(_nameserver, _port) = config.DNS_VERIFICATION_SERVER.split(":")
_root_dns = config.DNS_ROOT_DOMAIN
_resolver = dns.resolver.Resolver(configure=False)
_resolver.nameservers = [_nameserver]
_resolver.port = int(_port)


def get_cname(domain: str) -> str:
    result = ""
    try:
        answers = _resolver.resolve(domain, "CNAME")
        print(answers)

        result = answers[0].target.to_text(omit_final_dot=True)

    except dns.resolver.NXDOMAIN:
        logger.error("got NXDOMAIN for %s", domain)

    except dns.resolver.NoAnswer:
        logger.error("dns resolver got NoAnswer for %s", domain)

    except dns.exception.Timeout:
        logger.error("dns resolver got Timeout for %s", domain)

    except BaseException as e:
        logger.exception("dns resolver failed for %s", domain, exc_info=e)
    return result


def get_txt(domain: str) -> list:
    results = []
    try:
        answers = _resolver.resolve(domain, "TXT")
        for answer in answers:
            results.append(answer.to_text().strip('"'))

    except dns.resolver.NXDOMAIN:
        logger.error("dns resolver got NXDOMAIN for %s", domain)

    except dns.resolver.NoAnswer:
        logger.error("dns resolver got NoAnswer for %s", domain)

    except dns.exception.Timeout:
        logger.error("dns resolver got Timeout for %s", domain)

    except BaseException as e:
        logger.exception("dns resolver failed for %s", domain, exc_info=e)

    return results


def site_cname_target(domain: str) -> str:
    return f"{domain}.{_root_dns}"


def acme_challenge_cname_target(domain: str) -> str:
    return f"_acme-challenge.{domain}.{_root_dns}"


def acme_challenge_cname_name(domain: str) -> str:
    return f"_acme-challenge.{domain}"


def has_expected_cname(domain: str) -> bool:
    acme_good = get_cname(
        acme_challenge_cname_name(domain)
    ) == acme_challenge_cname_target(domain)
    site_good = get_cname(domain) == site_cname_target(domain)
    return acme_good and site_good


def has_expected_semaphore(domain: str) -> bool:
    return config.SEMAPHORE in get_txt(acme_challenge_cname_name(domain))

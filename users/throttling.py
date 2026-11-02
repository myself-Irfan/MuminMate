import ipaddress

from django.core.exceptions import SuspiciousOperation
from django.utils.crypto import salted_hmac

from users.models import User


def digest_email(email: str) -> str:
    normalized = User.objects.normalize_email(email)
    return salted_hmac("users.throttle_event", normalized, algorithm="sha256").hexdigest()


# Refuses (Django: 400) rather than skip: per-IP limits must not silently count nothing.
def mask_ip(address: str) -> str:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError as error:
        raise SuspiciousOperation("The client address is not an IP address.") from error
    if isinstance(ip, ipaddress.IPv4Address):
        return str(ip)
    if ip.ipv4_mapped:
        return str(ip.ipv4_mapped)
    # One IPv6 subscriber usually holds a whole /64.
    return str(ipaddress.ip_network(f"{ip}/64", strict=False).network_address)

import ipaddress

from django.contrib.auth import get_user_model
from django.utils.crypto import salted_hmac


def digest_email(email: str) -> str:
    normalized = get_user_model().objects.normalize_email(email)
    return salted_hmac("users.login_failure", normalized, algorithm="sha256").hexdigest()


def mask_ip(address: str) -> str:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv4Address):
        return str(ip)
    if ip.ipv4_mapped:
        return str(ip.ipv4_mapped)
    # One IPv6 subscriber usually holds a whole /64.
    return str(ipaddress.ip_network(f"{ip}/64", strict=False).network_address)

"""Validate customer-supplied database hosts (SSRF / rebinding mitigation)."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass

from app.tenant_store.exceptions import TenantHostRejected

_BLOCKED = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

DEFAULT_PORT = 5432
ALLOWED_PORTS = frozenset({5432, 5433, 5434})


@dataclass(frozen=True)
class ResolvedHost:
    hostname: str
    addresses: tuple[str, ...]
    port: int


def _is_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    for net in _BLOCKED:
        if addr in net:
            return True
    return False


def validate_host_port(
    host: str,
    port: int | None,
    *,
    allow_private: bool = False,
) -> ResolvedHost:
    host = (host or "").strip()
    if not host or len(host) > 255:
        raise TenantHostRejected("Host name is missing or too long.")
    port = port or DEFAULT_PORT
    if port not in ALLOWED_PORTS:
        raise TenantHostRejected(f"Port {port} is not allowed. Use one of: {sorted(ALLOWED_PORTS)}.")

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise TenantHostRejected("Could not resolve the host name. Check spelling and DNS.") from exc

    addrs: list[str] = []
    for info in infos:
        ip = info[4][0]
        addrs.append(ip)
        try:
            parsed = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if not allow_private and _is_blocked_ip(parsed):
            raise TenantHostRejected(
                "That address is not reachable with the public endpoint method. "
                "Use private connectivity or the secure connector instead."
            )

    if not addrs:
        raise TenantHostRejected("Host resolved to no usable addresses.")

    return ResolvedHost(hostname=host, addresses=tuple(sorted(set(addrs))), port=port)

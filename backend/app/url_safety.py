import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException


BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only public http/https URLs are supported.")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL must include a hostname.")
    host = parsed.hostname.lower().strip(".")
    if host in BLOCKED_HOSTS or host.endswith(".localhost"):
        raise HTTPException(status_code=400, detail="Local URLs are not allowed.")
    _validate_host_addresses(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    return parsed.geturl()


def _validate_host_addresses(host: str, port: int) -> None:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="Could not resolve URL hostname.") from exc

    if not infos:
        raise HTTPException(status_code=400, detail="Could not resolve URL hostname.")

    for info in infos:
        address = info[4][0]
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise HTTPException(status_code=400, detail="Private, local, or reserved network URLs are not allowed.")

"""Optional SOCKS proxy support for MongoDB connections.

When the ``MONGO_PROXY`` environment variable is set (for example ``socks5://host:port``), every TCP connection
PyMongo opens is routed through that proxy. TLS still runs end to end, on top of the proxied socket.
"""

from __future__ import annotations

import os
import socket

_INSTALLED = False


def install_socks_proxy() -> None:
    """Patch PyMongo's socket factory to connect through ``MONGO_PROXY``, if set."""
    global _INSTALLED  # noqa: PLW0603
    proxy_url = os.getenv("MONGO_PROXY")
    if _INSTALLED or not proxy_url:
        return

    from pymongo import pool_shared  # noqa: PLC0415
    from python_socks.sync import Proxy  # noqa: PLC0415

    original_create_connection = pool_shared._create_connection  # noqa: SLF001

    def _create_connection(address, options):  # noqa: ANN001, ANN202
        host, port = address
        if host.endswith(".sock"):
            return original_create_connection(address, options)
        timeout = options.connect_timeout
        sock = Proxy.from_url(proxy_url).connect(dest_host=host, dest_port=port or 27017, timeout=timeout)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, True)  # noqa: FBT003
        pool_shared._set_keepalive_times(sock)  # noqa: SLF001
        sock.settimeout(timeout)
        return sock

    pool_shared._create_connection = _create_connection  # noqa: SLF001
    _INSTALLED = True

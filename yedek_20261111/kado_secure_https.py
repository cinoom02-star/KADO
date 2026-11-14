# KADO_SECURE_HTTPS_V1
import http.client
import ipaddress
import socket
import ssl
import urllib.request
from urllib.parse import urlsplit

ALLOWED_HOSTS = frozenset({
    "kvkk.gov.tr",
    "www.kvkk.gov.tr",
})


def validate_url(url):
    parsed = urlsplit(url)

    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not parsed.netloc
    ):
        raise ValueError("Izinsiz HTTPS URL")

    return parsed.hostname


def resolve_safe_ips(host):
    if host not in ALLOWED_HOSTS:
        raise ValueError("Izinsiz alan adi")

    records = socket.getaddrinfo(
        host,
        443,
        type=socket.SOCK_STREAM,
    )

    addresses = []

    for record in records:
        ip = ipaddress.ip_address(record[4][0])

        if not ip.is_global:
            raise ValueError("Global olmayan DNS IP engellendi")

        addresses.append(str(ip))

    if not addresses:
        raise ValueError("DNS sonucu bos")

    return list(dict.fromkeys(addresses))


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, pinned_ip, **kwargs):
        if host not in ALLOWED_HOSTS:
            raise ValueError("Izinsiz alan adi")

        ip = ipaddress.ip_address(pinned_ip)

        if not ip.is_global:
            raise ValueError("Global olmayan IP engellendi")

        # KADO_PINNED_PORT_GUARD_V1
        port = kwargs.get("port", 443)
        if port is None:
            port = 443
        if port != 443 or isinstance(port, bool):
            raise ValueError("Yalnizca HTTPS 443 portuna izin verilir")

        self.pinned_ip = str(ip)
        super().__init__(host, **kwargs)

    def connect(self):
        if self._tunnel_host:
            raise ValueError("Proxy tunnel engellendi")

        self.sock = socket.create_connection(
            (self.pinned_ip, self.port),
            self.timeout,
            self.source_address,
        )

        try:
            self.sock = self._context.wrap_socket(
                self.sock,
                server_hostname=self.host,
            )
        except BaseException:
            self.sock.close()
            raise


class PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, context=None):
        self.context = context or ssl.create_default_context()
        super().__init__(context=self.context)

    def https_open(self, req):
        host = validate_url(req.full_url)
        ips = resolve_safe_ips(host)

        # DNS yeniden cozulmez: socket dogrudan IP'ye baglanir.
        pinned_ip = ips[0]

        def factory(request_host, **kwargs):
            return PinnedHTTPSConnection(
                request_host,
                pinned_ip,
                **kwargs,
            )

        return self.do_open(
            factory,
            req,
            context=self.context,
        )


def build_secure_opener(redirect_handler):
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        redirect_handler,
        PinnedHTTPSHandler(
            context=ssl.create_default_context()
        ),
    )

"""Server bind-address resolution for the ETAFlow API."""

from typing import Any, Mapping, Optional, Tuple

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def resolve_bind_address(
    cli_host: Optional[str],
    cli_port: Optional[int],
    config_api: Mapping[str, Any],
    environ: Mapping[str, str],
) -> Tuple[str, int]:
    """Pick host and port with precedence: CLI flags > API_HOST/API_PORT > config.yaml > defaults.

    Containers set API_HOST=0.0.0.0 so the server is reachable from outside the container.
    """
    host = str(config_api.get("host", DEFAULT_HOST))
    port = int(config_api.get("port", DEFAULT_PORT))

    if environ.get("API_HOST"):
        host = environ["API_HOST"]
    if environ.get("API_PORT"):
        raw_port = environ["API_PORT"]
        try:
            port = int(raw_port)
        except ValueError:
            raise ValueError(f"API_PORT must be an integer, got '{raw_port}'") from None

    if cli_host:
        host = cli_host
    if cli_port:
        port = int(cli_port)
    return host, port

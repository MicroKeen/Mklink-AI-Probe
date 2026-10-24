"""Small desktop endpoint helpers, independent of the device API."""
import json
import os
from pathlib import Path
import secrets


def _bind_desktop_server_socket(host: str, port: int, port_end: int):
    """Bind one loopback port and keep it reserved for Uvicorn."""
    import socket

    if host != "127.0.0.1":
        raise ValueError("desktop automatic ports require host 127.0.0.1")
    if not (1 <= port <= port_end <= 65535):
        raise ValueError("invalid desktop port range")

    last_error: OSError | None = None
    for candidate in range(port, port_end + 1):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if os.name == "nt":
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind((host, candidate))
            listener.listen(2048)
            return listener, candidate
        except OSError as exc:
            last_error = exc
            listener.close()
    raise OSError(
        f"no available desktop backend port in {port}..{port_end}"
    ) from last_error


def _write_desktop_runtime_info(
    path: str,
    *,
    port: int,
    instance_id: str,
) -> None:
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    try:
        temporary.write_text(
            json.dumps({"port": port, "instanceId": instance_id}),
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass



"""Negotiated loopback memory reads, with no reconnect or replay on failure."""
import json
import socket


class MemoryChannel:
    def __init__(self, info, session_id):
        from websockets.sync.client import connect
        self.connection = None
        raw = socket.create_connection(('127.0.0.1', info['port']), timeout=3)
        try:
            # websockets leaves a caller-owned socket's timeout unchanged.
            # Handshake/recv deadlines belong to the protocol, not idle TCP.
            raw.settimeout(None)
            self.connection = connect(
                f"ws://127.0.0.1:{info['port']}/_runtime/memory", sock=raw,
                additional_headers={'Authorization': 'Bearer ' + info['token'],
                                    'X-MKLink-Session': session_id,
                                    'X-MKLink-Probe': info.get('probe_id') or '',
                                    'X-MKLink-Instance': info['instance_id']},
                compression=None, open_timeout=3, close_timeout=1, max_size=65536,
            )
        except BaseException:
            raw.close()
            raise

    def read(self, arguments):
        from mklink.runtime import RuntimeErrorResponse
        self.connection.send(json.dumps(arguments).encode())
        response = json.loads(self.connection.recv(timeout=35))
        if not isinstance(response, dict) or type(response.get('status')) is not int:
            raise RuntimeErrorResponse('Invalid memory channel response; command was not retried')
        if response['status'] != 200:
            detail = response.get('detail', 'Memory request failed')
            raise RuntimeErrorResponse(str(detail), status_code=response['status'], detail=detail)
        if not isinstance(response.get('result'), dict):
            raise RuntimeErrorResponse('Missing memory result; command was not retried')
        return response['result']

    def close(self):
        if self.connection is not None:
            connection, self.connection = self.connection, None
            connection.close()

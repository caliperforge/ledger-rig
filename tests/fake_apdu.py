import socket
import threading


class FakeApdu:
    def __init__(self, replies: dict[bytes, bytes]) -> None:
        self._replies = replies
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        self._conn: socket.socket
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        self._conn, _ = self._listener.accept()
        self._listener.close()
        while header := self._conn.recv(4, socket.MSG_WAITALL):
            size = int.from_bytes(header, "big")
            reply = self._replies[self._conn.recv(size, socket.MSG_WAITALL)]
            self._conn.sendall((len(reply) - 2).to_bytes(4, "big") + reply)

    def close(self) -> None:
        self._conn.shutdown(socket.SHUT_RDWR)
        self._thread.join()
        self._conn.close()

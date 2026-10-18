import http.server
import socket
import subprocess
import threading

from conftest import PROCESS

SCRIPT = str(PROCESS / "web_portal.sh")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_check_fails_when_nothing_answers():
    p = subprocess.run(
        [SCRIPT, "--check", str(_free_port())], capture_output=True, text=True
    )
    assert p.returncode == 1
    assert "not 200" in p.stderr


def test_check_passes_on_200_and_fails_on_other_codes():
    class Handler(http.server.BaseHTTPRequestHandler):
        status = 200

        def do_GET(self):
            self.send_response(Handler.status)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = str(server.server_address[1])
    try:
        assert (
            subprocess.run([SCRIPT, "--check", port], capture_output=True).returncode
            == 0
        )
        Handler.status = 502
        assert (
            subprocess.run([SCRIPT, "--check", port], capture_output=True).returncode
            == 1
        )
    finally:
        server.shutdown()


def test_start_rejects_a_non_numeric_port():
    assert subprocess.run([SCRIPT, "abc"], capture_output=True).returncode in (1, 2)

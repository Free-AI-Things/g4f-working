"""Tests for g4f_tester.server (without spinning up a real g4f API)."""

import os, sys, socket, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from g4f_tester.server import (
    _is_port_open,
    _wait_for_server,
    cleanup_browsers,
    install_signal_hooks,
)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_is_port_open_false_for_unused_port():
    # Pick a port that's almost certainly closed.
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert _is_port_open("127.0.0.1", port, timeout=0.2) is False


def test_is_port_open_true_for_listening_port():
    port = _free_port()
    srv = HTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        time.sleep(0.2)
        assert _is_port_open("127.0.0.1", port, timeout=0.5) is True
    finally:
        srv.shutdown()


def test_wait_for_server_returns_true_when_200():
    port = _free_port()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        time.sleep(0.2)
        assert _wait_for_server(f"http://127.0.0.1:{port}/", timeout=3, interval=0.1) is True
    finally:
        srv.shutdown()


def test_wait_for_server_returns_false_when_unreachable():
    port = _free_port()
    # Never start a server on that port.
    assert _wait_for_server(f"http://127.0.0.1:{port}/", timeout=1, interval=0.1) is False


def test_cleanup_browsers_is_safe_when_nodriver_missing():
    # Should not raise even if nodriver is not installed.
    cleanup_browsers()


def test_install_signal_hooks_is_idempotent():
    install_signal_hooks()
    install_signal_hooks()
    install_signal_hooks()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  ... {name}", end=" ")
            fn()
            print("OK")
    print("All server tests passed.")

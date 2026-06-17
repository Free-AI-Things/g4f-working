"""g4f API server lifecycle + browser cleanup helpers.

This module wraps the two fragile side-effects of the legacy code:

* Starting ``g4f.api.run_api`` in a daemon thread.
* Cleaning up ``nodriver`` browser instances on exit.

The new implementation **polls** the server until it is reachable instead
of sleeping a fixed amount of time — this fixes the occasional GitHub
Actions flake where 5s wasn't enough for the server to bind.
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import socket
import threading
import time
from typing import Optional

import requests

from .config import Config

log = logging.getLogger(__name__)

# Track whether the atexit/signal hooks have been installed so we don't
# double-register when this module is imported multiple times.
_HOOKS_INSTALLED = False


def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """True when a TCP connection to (host, port) succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _wait_for_server(url: str, timeout: int, interval: float) -> bool:
    """Poll ``url`` until it responds 2xx or ``timeout`` seconds pass."""
    deadline = time.time() + timeout
    last_err: Optional[Exception] = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=interval)
            if r.status_code < 500:
                return True
        except requests.RequestException as e:
            last_err = e
        time.sleep(interval)
    if last_err:
        log.warning("Server at %s never responded: %s", url, last_err)
    return False


def cleanup_browsers() -> None:
    """Best-effort cleanup of leftover nodriver browser instances.

    Designed to be safe to call multiple times — every step is wrapped in
    its own try/except so a failure in one part never blocks the next.
    """
    try:
        try:
            from nodriver import util  # type: ignore
        except ImportError:
            return

        for browser in util.get_registered_instances():
            try:
                if getattr(browser, "connection", None):
                    browser.stop()
                    log.info("Stopped browser instance: %s", browser)
            except Exception as e:  # noqa: BLE001
                log.debug("Error stopping browser: %s", e)

        try:
            from g4f.cookies import get_cookies_dir  # type: ignore
            lock_file = os.path.join(get_cookies_dir(), ".nodriver_is_open")
            if os.path.exists(lock_file):
                os.remove(lock_file)
                log.info("Removed browser lock file: %s", lock_file)
        except Exception as e:  # noqa: BLE001
            log.debug("Error removing lock file: %s", e)
    except Exception as e:  # noqa: BLE001
        log.debug("Error during browser cleanup: %s", e)


def install_signal_hooks() -> None:
    """Register atexit + SIGTERM/SIGINT hooks (idempotent)."""
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return
    atexit.register(cleanup_browsers)
    # SIGTERM/SIGINT are not available on Windows in the same way; guard.
    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                signal.signal(sig, lambda *_: cleanup_browsers())
            except (ValueError, RuntimeError):
                # Not in main thread — skip silently.
                pass
    _HOOKS_INSTALLED = True


def start_g4f_api_server(
    port: int = 8081,
    api_key: Optional[str] = None,
    *,
    poll_timeout: int = 60,
    poll_interval: float = 0.5,
) -> Optional[threading.Thread]:
    """Start the g4f API server in a daemon thread.

    Returns the thread object (or ``None`` if the import failed). The
    function blocks until the server responds to HTTP requests or until
    ``poll_timeout`` seconds elapse.
    """
    try:
        import g4f.api  # type: ignore
    except ImportError as e:
        log.error("g4f.api is not installed: %s", e)
        return None

    def _run() -> None:
        try:
            if api_key:
                g4f.api.AppConfig.set_config(g4f_api_key=api_key)
            g4f.api.run_api(port=port, debug=True)
        except Exception as e:  # noqa: BLE001
            log.error("Error starting g4f API server: %s", e)

    thread = threading.Thread(target=_run, daemon=True, name="g4f-api-server")
    thread.start()

    # Always install cleanup hooks — cheap and idempotent.
    install_signal_hooks()

    print(f"Starting g4f API server on port {port}...")
    # Fast path: wait for the TCP port to come up first.
    deadline_tcp = time.time() + min(poll_timeout, 15)
    while time.time() < deadline_tcp:
        if _is_port_open("127.0.0.1", port):
            break
        time.sleep(poll_interval)

    ready = _wait_for_server(
        f"http://127.0.0.1:{port}/v1/providers",
        timeout=poll_timeout,
        interval=poll_interval,
    )
    if ready:
        print(f"g4f API server is ready on port {port}.")
    else:
        # Don't hard-fail — older behaviour kept going too. The fetcher
        # will surface a clear error if the server really isn't there.
        print(f"WARNING: g4f API server on port {port} did not confirm readiness "
              f"within {poll_timeout}s — continuing anyway.")
    return thread


def start_server_from_config(cfg: Config) -> Optional[threading.Thread]:
    """Convenience wrapper that pulls settings from a :class:`Config`."""
    return start_g4f_api_server(
        port=cfg.port,
        api_key=cfg.api_key,
        poll_timeout=cfg.server_poll_timeout,
        poll_interval=cfg.server_poll_interval,
    )

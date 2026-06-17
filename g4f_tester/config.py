"""Centralised configuration for the g4f_tester package.

A single :class:`Config` instance is constructed from (in priority order):

1. Explicit constructor arguments.
2. Environment variables (``G4F_*``).
3. Hard-coded defaults that match the legacy behaviour.

This means the GitHub Actions workflow keeps working unchanged, while
power users can override anything they like without touching code.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Constants — kept here so every module agrees on the same names.
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = "http://localhost:8081"
DEFAULT_API_KEY = "1234"
DEFAULT_PORT = 8081
DEFAULT_MAX_CONCURRENT = 50
DEFAULT_TIMEOUT = 120          # seconds, per request
DEFAULT_BATCH_SIZE = 20
DEFAULT_SERVER_WAIT = 5        # seconds, between server-start polls
DEFAULT_SERVER_WAIT_GHA = 15   # seconds, in GitHub Actions (slower runners)
SERVER_POLL_INTERVAL = 0.5     # seconds, between readiness probes
SERVER_POLL_TIMEOUT = 60       # seconds, max wait for server to come up

PROVIDER_DIR = "provider"
WORKING_DIR = "working"
OUTPUT_DIR = "output"
GENERATED_MEDIA_DIR = "generated_media"

DEFAULT_TEST_MESSAGE = "Hello, are you working? Reply with 'Yes' if you can respond."
DEFAULT_IMAGE_PROMPT = "a simple test image of a red apple"
DEFAULT_VIDEO_PROMPT = "a simple test video of a cat walking"
DEFAULT_AUDIO_PROMPT = "Hello, this is a test audio generation"

# Keyword sets used to guess a model's capabilities from its name when the
# API doesn't return explicit ``image``/``audio``/``video`` flags.
VIDEO_KEYWORDS: tuple = (
    "video", "sora", "cogvideo", "mochi", "hunyuan", "ltx-video", "wan2.1",
)
AUDIO_KEYWORDS: tuple = (
    "audio", "tts", "speech", "voice", "gtts", "openai-audio",
)
IMAGE_KEYWORDS: tuple = (
    "flux", "dall", "stable", "image", "draw", "paint", "midjourney", "diffusion",
)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read an environment variable, treating empty string as missing."""
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return val


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Config:
    """Runtime configuration for the fetcher/tester/reporter pipeline."""

    base_url: str = DEFAULT_BASE_URL
    api_key: Optional[str] = DEFAULT_API_KEY
    port: int = DEFAULT_PORT
    max_concurrent: int = DEFAULT_MAX_CONCURRENT
    timeout: int = DEFAULT_TIMEOUT
    batch_size: int = DEFAULT_BATCH_SIZE
    provider_dir: str = PROVIDER_DIR
    working_dir: str = WORKING_DIR
    output_dir: str = OUTPUT_DIR
    generated_media_dir: str = GENERATED_MEDIA_DIR
    test_message: str = DEFAULT_TEST_MESSAGE
    image_prompt: str = DEFAULT_IMAGE_PROMPT
    video_prompt: str = DEFAULT_VIDEO_PROMPT
    audio_prompt: str = DEFAULT_AUDIO_PROMPT
    start_server: bool = True
    server_poll_timeout: int = SERVER_POLL_TIMEOUT
    server_poll_interval: float = SERVER_POLL_INTERVAL
    cleanup_browser_every_n_batches: int = 10
    inter_batch_sleep: float = 3.0
    # Optional list of provider names to skip (useful for debugging).
    skip_providers: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_env(cls, **overrides) -> "Config":
        """Build a Config from environment variables + optional overrides."""
        kwargs = dict(
            base_url=_env("G4F_BASE_URL", DEFAULT_BASE_URL),
            api_key=_env("G4F_API_KEY", DEFAULT_API_KEY),
            port=_env_int("G4F_PORT", DEFAULT_PORT),
            max_concurrent=_env_int("G4F_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT),
            timeout=_env_int("G4F_TIMEOUT", DEFAULT_TIMEOUT),
            batch_size=_env_int("G4F_BATCH_SIZE", DEFAULT_BATCH_SIZE),
            test_message=_env("G4F_TEST_MESSAGE", DEFAULT_TEST_MESSAGE),
            image_prompt=_env("G4F_IMAGE_PROMPT", DEFAULT_IMAGE_PROMPT),
            video_prompt=_env("G4F_VIDEO_PROMPT", DEFAULT_VIDEO_PROMPT),
            audio_prompt=_env("G4F_AUDIO_PROMPT", DEFAULT_AUDIO_PROMPT),
            start_server=not _env_bool("G4F_NO_SERVER", False),
        )
        kwargs.update(overrides)
        return cls(**kwargs)

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "Config":
        """Build a Config from a parsed argparse Namespace."""
        return cls(
            base_url=args.base_url,
            api_key=args.api_key,
            port=args.port,
            max_concurrent=args.max_concurrent,
            timeout=args.timeout,
            batch_size=args.batch_size,
            provider_dir=args.provider_dir,
            working_dir=args.working_dir,
            output_dir=args.output_dir,
            start_server=not args.no_server,
            test_message=args.test_message,
            image_prompt=args.image_prompt,
            video_prompt=args.video_prompt,
            audio_prompt=args.audio_prompt,
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def auth_headers(self) -> dict:
        """HTTP headers needed to authenticate against the g4f API."""
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    @property
    def is_github_actions(self) -> bool:
        """True when running inside GitHub Actions."""
        return os.getenv("GITHUB_ACTIONS") == "true"

    def ensure_dirs(self) -> None:
        """Create every output directory used by the pipeline."""
        for d in (
            self.provider_dir,
            self.working_dir,
            self.output_dir,
            self.generated_media_dir,
        ):
            os.makedirs(d, exist_ok=True)


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser used by ``provider_tester.py``."""
    p = argparse.ArgumentParser(
        prog="provider_tester",
        description="Test which gpt4free providers/models work without auth.",
    )
    p.add_argument("--base-url", default=DEFAULT_BASE_URL,
                   help=f"g4f API base URL (default: {DEFAULT_BASE_URL})")
    p.add_argument("--api-key", default=DEFAULT_API_KEY,
                   help=f"API key passed to g4f (default: {DEFAULT_API_KEY})")
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help=f"Port to run the g4f API on (default: {DEFAULT_PORT})")
    p.add_argument("--max-concurrent", type=int, default=DEFAULT_MAX_CONCURRENT,
                   help=f"Max concurrent test requests (default: {DEFAULT_MAX_CONCURRENT})")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help=f"Per-request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                   help=f"Test batch size (default: {DEFAULT_BATCH_SIZE})")
    p.add_argument("--provider-dir", default=PROVIDER_DIR,
                   help=f"Directory for provider metadata (default: {PROVIDER_DIR})")
    p.add_argument("--working-dir", default=WORKING_DIR,
                   help=f"Directory for working results (default: {WORKING_DIR})")
    p.add_argument("--output-dir", default=OUTPUT_DIR,
                   help=f"Directory for raw outputs (default: {OUTPUT_DIR})")
    p.add_argument("--no-server", action="store_true",
                   help="Don't start the embedded g4f API server (use --base-url instead)")
    p.add_argument("--test-message", default=DEFAULT_TEST_MESSAGE,
                   help="Prompt used for text capability tests")
    p.add_argument("--image-prompt", default=DEFAULT_IMAGE_PROMPT,
                   help="Prompt used for image generation tests")
    p.add_argument("--video-prompt", default=DEFAULT_VIDEO_PROMPT,
                   help="Prompt used for video generation tests")
    p.add_argument("--audio-prompt", default=DEFAULT_AUDIO_PROMPT,
                   help="Prompt used for audio generation tests")
    return p


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI args (wrapper around build_arg_parser for testability)."""
    return build_arg_parser().parse_args(argv)

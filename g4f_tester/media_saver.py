"""Media-saving helpers — consolidates the six duplicated save_* methods
from the legacy single-file implementation into one cohesive class.

All public methods are async and silent on failure (errors are logged at
debug level) so a flaky media download never aborts a test run.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Iterable, Optional, Union

import aiohttp

log = logging.getLogger(__name__)


def _safe_name(name: str) -> str:
    """Make a model/provider name safe to use as a filename component."""
    return name.replace("/", "_").replace("\\", "_")


def _join_url(base_url: str, url: str) -> str:
    """Resolve a possibly-relative URL against the API base URL."""
    if url.startswith("/"):
        return f"{base_url.rstrip('/')}{url}"
    return url


class MediaSaver:
    """Persist text / image / video / audio responses to disk.

    The saver is stateless beyond its config — every public method takes
    everything it needs as arguments so it's trivially testable.
    """

    def __init__(self, output_dir: str, base_url: str = "") -> None:
        self.output_dir = output_dir
        self.base_url = base_url
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _path(self, provider: str, model: str, suffix: str, ext: str) -> str:
        fname = f"{_safe_name(provider)}_{_safe_name(model)}_{suffix}.{ext}"
        return os.path.join(self.output_dir, fname)

    @staticmethod
    def _decode_data_url(data_url: str) -> bytes:
        """Decode a ``data:...;base64,<...>`` URL into raw bytes."""
        if "," in data_url:
            data_url = data_url.split(",", 1)[1]
        return base64.b64decode(data_url)

    async def _download(self, session: aiohttp.ClientSession, url: str, filepath: str) -> bool:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    log.debug("GET %s -> HTTP %s", url, response.status)
                    return False
                with open(filepath, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                log.info("Saved media: %s", filepath)
                return True
        except Exception as e:  # noqa: BLE001
            log.debug("Error downloading %s: %s", url, e)
            return False

    async def _write_bytes(self, filepath: str, data: bytes) -> bool:
        try:
            with open(filepath, "wb") as f:
                f.write(data)
            log.info("Saved media: %s", filepath)
            return True
        except Exception as e:  # noqa: BLE001
            log.debug("Error writing %s: %s", filepath, e)
            return False

    async def _write_text(self, filepath: str, text: str) -> bool:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
            log.info("Saved text: %s", filepath)
            return True
        except Exception as e:  # noqa: BLE001
            log.debug("Error writing %s: %s", filepath, e)
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def save_text(self, provider: str, model: str, content: str) -> bool:
        filepath = self._path(provider, model, "response", "txt")
        return await self._write_text(filepath, content)

    async def save_image_url(
        self,
        provider: str,
        model: str,
        image_url: str,
        index: int = 0,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> bool:
        filepath = self._path(provider, model, f"image_{index}", "jpg")
        return await self._save_media_url(image_url, filepath, session)

    async def save_video_url(
        self,
        provider: str,
        model: str,
        video_url: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> bool:
        filepath = self._path(provider, model, "video", "mp4")
        return await self._save_media_url(video_url, filepath, session)

    async def save_audio_bytes(self, provider: str, model: str, audio_data: bytes) -> bool:
        filepath = self._path(provider, model, "audio", "mp3")
        return await self._write_bytes(filepath, audio_data)

    async def save_audio_url(
        self,
        provider: str,
        model: str,
        audio_url: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> bool:
        filepath = self._path(provider, model, "audio", "mp3")
        return await self._save_media_url(audio_url, filepath, session)

    async def save_image_data_url(self, provider: str, model: str, data_url: str, index: int = 0) -> bool:
        filepath = self._path(provider, model, f"image_{index}", "jpg")
        try:
            return await self._write_bytes(filepath, self._decode_data_url(data_url))
        except Exception as e:  # noqa: BLE001
            log.debug("Error decoding image data URL for %s_%s: %s", provider, model, e)
            return False

    async def save_audio_data_url(self, provider: str, model: str, data_url: str) -> bool:
        filepath = self._path(provider, model, "audio", "mp3")
        try:
            return await self._write_bytes(filepath, self._decode_data_url(data_url))
        except Exception as e:  # noqa: BLE001
            log.debug("Error decoding audio data URL for %s_%s: %s", provider, model, e)
            return False

    async def save_image_responses(
        self,
        provider: str,
        model: str,
        images: Iterable[str],
        session: Optional[aiohttp.ClientSession] = None,
    ) -> int:
        """Save every image in ``images``. Returns count actually saved."""
        saved = 0
        for i, image_url in enumerate(images):
            ok = False
            try:
                if isinstance(image_url, str) and image_url.startswith("data:"):
                    ok = await self.save_image_data_url(provider, model, image_url, i)
                elif isinstance(image_url, str) and image_url.startswith(("http://", "https://", "/")):
                    ok = await self.save_image_url(provider, model, image_url, i, session)
            except Exception as e:  # noqa: BLE001
                log.debug("Error saving image %d for %s_%s: %s", i, provider, model, e)
            if ok:
                saved += 1
        return saved

    async def save_audio_response(
        self,
        provider: str,
        model: str,
        audio_data: Union[dict, str, bytes],
        session: Optional[aiohttp.ClientSession] = None,
    ) -> bool:
        """Save an audio response that may be a dict, data URL, or raw bytes."""
        if isinstance(audio_data, bytes):
            return await self.save_audio_bytes(provider, model, audio_data)
        if isinstance(audio_data, str):
            if audio_data.startswith("data:"):
                return await self.save_audio_data_url(provider, model, audio_data)
            if audio_data.startswith(("http://", "https://", "/")):
                return await self.save_audio_url(provider, model, audio_data, session)
        if isinstance(audio_data, dict):
            payload = audio_data.get("data") or audio_data.get("url")
            if payload:
                return await self.save_audio_response(provider, model, payload, session)
        log.debug("Unrecognised audio payload shape for %s_%s", provider, model)
        return False

    async def save_video_response(
        self,
        provider: str,
        model: str,
        video_data: Union[dict, str],
        session: Optional[aiohttp.ClientSession] = None,
    ) -> bool:
        """Save a video response (dict with ``url`` key, or a URL string)."""
        if isinstance(video_data, str):
            return await self.save_video_url(provider, model, video_data, session)
        if isinstance(video_data, dict):
            url = video_data.get("url")
            if url:
                return await self.save_video_url(provider, model, url, session)
        log.debug("Unrecognised video payload shape for %s_%s", provider, model)
        return False

    # ------------------------------------------------------------------
    # Shared downloader (handles data: / http(s): / relative /media/...)
    # ------------------------------------------------------------------
    async def _save_media_url(
        self,
        url: str,
        filepath: str,
        session: Optional[aiohttp.ClientSession],
    ) -> bool:
        if not url:
            return False
        if url.startswith("data:"):
            try:
                return await self._write_bytes(filepath, self._decode_data_url(url))
            except Exception as e:  # noqa: BLE001
                log.debug("Error decoding data URL: %s", e)
                return False
        if not url.startswith(("http://", "https://", "/")):
            log.debug("Unsupported URL scheme: %s", url[:50])
            return False
        full_url = _join_url(self.base_url, url) if url.startswith("/") else url
        owns_session = session is None
        if owns_session:
            async with aiohttp.ClientSession() as session:
                return await self._download(session, full_url, filepath)
        return await self._download(session, full_url, filepath)

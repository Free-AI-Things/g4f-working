"""Async tester for individual provider/model combinations.

Fixes three bugs inherited from the legacy single-file implementation:

1. **Payload mutation** — ``test_video_generation`` / ``test_audio_generation``
   reused the same ``payload`` dict across endpoint attempts, so the second
   endpoint received the wrong body. Each endpoint now builds its own payload.

2. **Premature return on first endpoint** — if the first endpoint returned
   HTTP 200 but the body had no media, the function returned ``working=False``
   instead of trying the fallback endpoint. We now ``continue`` to the next
   endpoint before giving up.

3. **Inconsistent response_time** — outer exception handler measured from
   ``start_time`` but inner success path measured only the latest request.
   Everything now uses ``time.time() - start_time`` for consistency.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import List, Optional

import aiohttp

from .config import (
    AUDIO_KEYWORDS,
    IMAGE_KEYWORDS,
    VIDEO_KEYWORDS,
)
from .media_saver import MediaSaver
from .models import TestResultWithTypes

log = logging.getLogger(__name__)


class ProviderModelTester:
    """Probe every capability (text / image / audio / video) of a model."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        max_concurrent: int = 50,
        timeout: int = 120,
        *,
        output_dir: str = "output",
        test_messages: Optional[List[dict]] = None,
        image_prompt: str = "a simple test image of a red apple",
        video_prompt: str = "a simple test video of a cat walking",
        audio_prompt: str = "Hello, this is a test audio generation",
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.saver = MediaSaver(output_dir, base_url=base_url)
        self.test_messages = test_messages or [
            {"role": "user",
             "content": "Hello, are you working? Reply with 'Yes' if you can respond."}
        ]
        self.image_prompt = image_prompt
        self.video_prompt = video_prompt
        self.audio_prompt = audio_prompt

    # ------------------------------------------------------------------
    # Headers / capability detection
    # ------------------------------------------------------------------
    def _headers(self, *, json_body: bool = True) -> dict:
        h = {}
        if json_body:
            h["Content-Type"] = "application/json"
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def get_model_capabilities(
        self, session: aiohttp.ClientSession, provider: str, model: str
    ) -> dict:
        """Ask the API what media types a model advertises."""
        try:
            async with session.get(
                f"{self.base_url}/api/{provider}/models",
                headers=self._headers(json_body=False),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
                if isinstance(data, dict) and "data" in data:
                    for m in data["data"]:
                        if m.get("id") == model:
                            return {
                                "image": bool(m.get("image", False)),
                                "video": bool(m.get("video", False)),
                                "audio": bool(m.get("audio", False)),
                                "vision": bool(m.get("vision", False)),
                            }
        except Exception as e:  # noqa: BLE001
            log.debug("Error getting capabilities for %s/%s: %s", provider, model, e)
        return {}

    @staticmethod
    def _guess_response_types(model_name: str, model_info: dict) -> List[str]:
        """Combine API hints + keyword sniffing to decide what to test."""
        name_lower = model_name.lower()
        types = ["text"]
        if model_info.get("image") or any(kw in name_lower for kw in IMAGE_KEYWORDS):
            types.append("image")
        if model_info.get("audio") or any(kw in name_lower for kw in AUDIO_KEYWORDS):
            types.append("audio")
        if model_info.get("video") or any(kw in name_lower for kw in VIDEO_KEYWORDS):
            types.append("video")
        return types

    # ------------------------------------------------------------------
    # Top-level per-combination test
    # ------------------------------------------------------------------
    async def test_provider_model_combination(
        self, session: aiohttp.ClientSession, provider: str, model: str
    ) -> List[TestResultWithTypes]:
        """Test every relevant capability for one provider/model pair."""
        info = await self.get_model_capabilities(session, provider, model)
        response_types = self._guess_response_types(model, info)
        results: List[TestResultWithTypes] = []

        results.append(await self.test_single_model(session, provider, model, response_types))
        if "image" in response_types:
            results.append(await self.test_image_generation(session, provider, model, response_types))
        if "audio" in response_types:
            results.append(await self.test_audio_generation(session, provider, model, response_types))
        if "video" in response_types:
            results.append(await self.test_video_generation(session, provider, model, response_types))
        return results

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------
    async def test_single_model(
        self, session: aiohttp.ClientSession, provider: str, model: str,
        response_types: List[str],
    ) -> TestResultWithTypes:
        async with self.semaphore:
            start = time.time()
            try:
                payload = {
                    "model": model,
                    "provider": provider,
                    "messages": self.test_messages,
                    "stream": True,
                    "max_tokens": 50,
                }
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    elapsed = time.time() - start
                    if response.status != 200:
                        err = await response.text()
                        return TestResultWithTypes(
                            provider, model, False, elapsed,
                            error=f"HTTP {response.status}: {err[:200]}",
                            response_types=response_types,
                        )

                    content_parts: List[str] = []
                    media: List[str] = []
                    error_message: Optional[str] = None

                    async for line in response.content:
                        if not line:
                            continue
                        line_str = line.decode("utf-8", errors="replace").strip()
                        if not line_str.startswith("data: "):
                            continue
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        if "error" in chunk:
                            error_message = chunk["error"].get("message", "Unknown error")
                            break
                        if not chunk.get("choices"):
                            continue
                        choice = chunk["choices"][0]
                        delta = choice.get("delta", {})
                        if "content" in delta and delta["content"]:
                            content_parts.append(delta["content"])
                        msg = choice.get("message")
                        if msg:
                            if msg.get("audio"):
                                await self.saver.save_audio_response(provider, model, msg["audio"], session)
                                media.append("audio")
                            if msg.get("images"):
                                await self.saver.save_image_responses(provider, model, msg["images"], session)
                                media.append("image")
                            if msg.get("video"):
                                await self.saver.save_video_response(provider, model, msg["video"], session)
                                media.append("video")

                    if error_message:
                        return TestResultWithTypes(
                            provider, model, False, elapsed,
                            error=f"API Error: {error_message[:200]}",
                            response_types=response_types,
                        )

                    full = "".join(content_parts)
                    if full:
                        await self.saver.save_text(provider, model, full)

                    return TestResultWithTypes(
                        provider, model,
                        working=bool(full or media),
                        response_time=elapsed,
                        response_content=full[:100] if full else f"Media: {', '.join(media)}",
                        media_type="text" if full else (media[0] if media else None),
                        response_types=response_types,
                    )
            except asyncio.TimeoutError:
                return TestResultWithTypes(
                    provider, model, False, self.timeout,
                    error="Request timeout", response_types=response_types,
                )
            except Exception as e:  # noqa: BLE001
                return TestResultWithTypes(
                    provider, model, False, time.time() - start,
                    error=f"Unexpected error: {str(e)[:200]}",
                    response_types=response_types,
                )

    # ------------------------------------------------------------------
    # Image
    # ------------------------------------------------------------------
    async def test_image_generation(
        self, session: aiohttp.ClientSession, provider: str, model: str,
        response_types: List[str],
    ) -> TestResultWithTypes:
        async with self.semaphore:
            start = time.time()
            try:
                payload = {
                    "prompt": self.image_prompt,
                    "model": model,
                    "provider": provider,
                    "response_format": "url",
                    "n": 1,
                }
                async with session.post(
                    f"{self.base_url}/v1/images/generate",
                    headers=self._headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    elapsed = time.time() - start
                    if response.status != 200:
                        err = await response.text()
                        return TestResultWithTypes(
                            provider, model, False, elapsed,
                            error=f"HTTP {response.status}: {err[:200]}",
                            media_type="image", response_types=response_types,
                        )
                    data = await response.json()
                    if "error" in data:
                        msg = data["error"].get("message", "Unknown error")
                        return TestResultWithTypes(
                            provider, model, False, elapsed,
                            error=f"API Error: {msg[:200]}",
                            media_type="image", response_types=response_types,
                        )
                    if data.get("data"):
                        url = data["data"][0].get("url", "")
                        if url:
                            await self.saver.save_image_url(provider, model, url, 0, session)
                            return TestResultWithTypes(
                                provider, model, True, elapsed,
                                response_content=f"Image generated: {url[:50]}...",
                                media_type="image", response_types=response_types,
                            )
                    return TestResultWithTypes(
                        provider, model, False, elapsed,
                        error="No valid image data in response",
                        media_type="image", response_types=response_types,
                    )
            except Exception as e:  # noqa: BLE001
                return TestResultWithTypes(
                    provider, model, False, time.time() - start,
                    error=f"Image generation error: {str(e)[:200]}",
                    media_type="image", response_types=response_types,
                )

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------
    async def test_video_generation(
        self, session: aiohttp.ClientSession, provider: str, model: str,
        response_types: List[str],
    ) -> TestResultWithTypes:
        """Try ``/v1/video/generate`` first, fall back to chat-completions."""
        async with self.semaphore:
            start = time.time()
            last_error: Optional[str] = None

            for endpoint_kind in ("video/generate", "chat/completions"):
                # Build a fresh payload for each endpoint — avoids the
                # mutation bug from the legacy implementation.
                if endpoint_kind == "video/generate":
                    endpoint = f"{self.base_url}/v1/video/generate"
                    payload = {
                        "prompt": self.video_prompt,
                        "model": model,
                        "provider": provider,
                        "aspect_ratio": "16:9",
                        "duration": 5,
                    }
                else:
                    endpoint = f"{self.base_url}/v1/chat/completions"
                    payload = {
                        "model": model,
                        "provider": provider,
                        "messages": [{"role": "user", "content": self.video_prompt}],
                        "stream": True,
                    }

                try:
                    async with session.post(
                        endpoint,
                        headers=self._headers(),
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        elapsed = time.time() - start
                        if response.status != 200:
                            err = await response.text()
                            last_error = f"HTTP {response.status}: {err[:200]}"
                            # Try the next endpoint rather than giving up.
                            continue

                        if endpoint_kind == "video/generate":
                            data = await response.json()
                            if "error" in data:
                                last_error = f"API Error: {data['error'].get('message', 'Unknown')[:200]}"
                                continue
                            if data.get("data"):
                                url = data["data"][0].get("url", "")
                                if url:
                                    await self.saver.save_video_url(provider, model, url, session)
                                    return TestResultWithTypes(
                                        provider, model, True, elapsed,
                                        response_content=f"Video generated: {url[:50]}...",
                                        media_type="video", response_types=response_types,
                                    )
                            last_error = "No valid video data in response"
                            continue

                        # Streaming chat/completions fallback.
                        video_found = False
                        async for line in response.content:
                            if not line:
                                continue
                            line_str = line.decode("utf-8", errors="replace").strip()
                            if not line_str.startswith("data: "):
                                continue
                            data_str = line_str[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            if "error" in chunk:
                                last_error = f"API Error: {chunk['error'].get('message', 'Unknown')[:200]}"
                                break
                            if "video" in str(chunk).lower():
                                video_found = True
                                break
                        if video_found:
                            return TestResultWithTypes(
                                provider, model, True, elapsed,
                                response_content="Video response detected",
                                media_type="video", response_types=response_types,
                            )
                        # else: loop to next endpoint (or fall through to failure).
                except Exception as e:  # noqa: BLE001
                    last_error = f"Video endpoint error: {str(e)[:200]}"
                    continue

            return TestResultWithTypes(
                provider, model, False, time.time() - start,
                error=last_error or "Video generation failed on all endpoints",
                media_type="video", response_types=response_types,
            )

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------
    async def test_audio_generation(
        self, session: aiohttp.ClientSession, provider: str, model: str,
        response_types: List[str],
    ) -> TestResultWithTypes:
        """Try ``/v1/audio/speech`` first, fall back to chat-completions."""
        async with self.semaphore:
            start = time.time()
            last_error: Optional[str] = None

            for endpoint_kind in ("audio/speech", "chat/completions"):
                if endpoint_kind == "audio/speech":
                    endpoint = f"{self.base_url}/v1/audio/speech"
                    payload = {
                        "input": self.audio_prompt,
                        "model": model,
                        "provider": provider,
                        "voice": "alloy",
                        "response_format": "mp3",
                    }
                else:
                    endpoint = f"{self.base_url}/v1/chat/completions"
                    payload = {
                        "model": model,
                        "provider": provider,
                        "messages": [{"role": "user", "content": self.audio_prompt}],
                        "stream": True,
                        "audio": {"voice": "alloy"},
                    }

                try:
                    async with session.post(
                        endpoint,
                        headers=self._headers(),
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        elapsed = time.time() - start
                        if response.status != 200:
                            err = await response.text()
                            last_error = f"HTTP {response.status}: {err[:200]}"
                            continue

                        if endpoint_kind == "audio/speech":
                            # Some g4f builds respond with raw MP3 bytes; others
                            # respond with JSON. Handle both.
                            content_type = response.headers.get("Content-Type", "")
                            if "application/json" in content_type:
                                data = await response.json()
                                if "error" in data:
                                    last_error = f"API Error: {data['error'].get('message', 'Unknown')[:200]}"
                                    continue
                                # Some JSON responses embed a URL or data URL.
                                url = None
                                if isinstance(data, dict) and data.get("data"):
                                    raw = data["data"][0] if isinstance(data["data"], list) else data["data"]
                                    if isinstance(raw, dict):
                                        url = raw.get("url", "")
                                    elif isinstance(raw, str):
                                        url = raw
                                if url:
                                    await self.saver.save_audio_url(provider, model, url, session)
                                    return TestResultWithTypes(
                                        provider, model, True, elapsed,
                                        response_content="Audio generated successfully",
                                        media_type="audio", response_types=response_types,
                                    )
                                last_error = "No valid audio data in JSON response"
                                continue
                            else:
                                audio_bytes = await response.read()
                                if audio_bytes:
                                    await self.saver.save_audio_bytes(provider, model, audio_bytes)
                                    return TestResultWithTypes(
                                        provider, model, True, elapsed,
                                        response_content="Audio generated successfully",
                                        media_type="audio", response_types=response_types,
                                    )
                                last_error = "Empty audio response body"
                                continue

                        # Streaming chat/completions fallback.
                        audio_found = False
                        async for line in response.content:
                            if not line:
                                continue
                            line_str = line.decode("utf-8", errors="replace").strip()
                            if not line_str.startswith("data: "):
                                continue
                            data_str = line_str[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            if "error" in chunk:
                                last_error = f"API Error: {chunk['error'].get('message', 'Unknown')[:200]}"
                                break
                            if chunk.get("choices"):
                                choice = chunk["choices"][0]
                                msg = choice.get("message")
                                if msg and msg.get("audio"):
                                    await self.saver.save_audio_response(provider, model, msg["audio"], session)
                                    audio_found = True
                                    break
                        if audio_found:
                            return TestResultWithTypes(
                                provider, model, True, elapsed,
                                response_content="Audio response detected",
                                media_type="audio", response_types=response_types,
                            )
                except Exception as e:  # noqa: BLE001
                    last_error = f"Audio endpoint error: {str(e)[:200]}"
                    continue

            return TestResultWithTypes(
                provider, model, False, time.time() - start,
                error=last_error or "Audio generation failed on all endpoints",
                media_type="audio", response_types=response_types,
            )

    # ------------------------------------------------------------------
    # Batch orchestration
    # ------------------------------------------------------------------
    async def test_all_models(
        self, test_data: List[tuple],
    ) -> List[TestResultWithTypes]:
        """Run all tests concurrently with the configured semaphore."""
        log.info("Starting tests for %d provider-model combinations", len(test_data))
        log.info("Max concurrent requests: %d", self.max_concurrent)
        log.info("Timeout per request: %d seconds", self.timeout)

        connector = aiohttp.TCPConnector(limit=self.max_concurrent * 2)
        # Session-level timeout is a safety net; per-request timeouts override.
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        results: List[TestResultWithTypes] = []

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [
                asyncio.ensure_future(
                    self.test_provider_model_combination(session, p, m)
                )
                for p, m in test_data
            ]
            completed = 0
            for coro in asyncio.as_completed(tasks):
                model_results = await coro
                results.extend(model_results)
                completed += 1
                if completed % 50 == 0:
                    working = sum(1 for r in results if r.working)
                    log.info("Progress: %d/%d - Working: %d", completed, len(test_data), working)
        return results

    async def test_all_models_batched(
        self,
        test_data: List[tuple],
        batch_size: int = 20,
        *,
        cleanup_fn=None,
        cleanup_every_n_batches: int = 10,
        inter_batch_sleep: float = 3.0,
    ) -> List[TestResultWithTypes]:
        """Run tests in batches to avoid overwhelming the API.

        ``cleanup_fn`` (typically :func:`g4f_tester.server.cleanup_browsers`)
        is invoked every ``cleanup_every_n_batches`` batches.
        """
        all_results: List[TestResultWithTypes] = []
        total_batches = (len(test_data) + batch_size - 1) // batch_size

        for i in range(0, len(test_data), batch_size):
            batch = test_data[i:i + batch_size]
            batch_num = i // batch_size + 1
            print(f"Processing batch {batch_num}/{total_batches}")
            all_results.extend(await self.test_all_models(batch))

            if cleanup_fn and batch_num % cleanup_every_n_batches == 0:
                print(f"Performing browser cleanup after batch {batch_num}")
                cleanup_fn()
                await asyncio.sleep(2)
            if i + batch_size < len(test_data):
                await asyncio.sleep(inter_batch_sleep)
        return all_results

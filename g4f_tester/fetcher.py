"""Fetch the list of providers and their models from the g4f API.

Consolidates ``fetch_providers_and_models`` and
``fetch_providers_and_models_with_types`` from the legacy code into one
parameterised method. The default behaviour (``with_types=False``) is
byte-for-byte compatible with what the legacy ``main()`` produced.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Tuple

import requests

from .config import (
    AUDIO_KEYWORDS,
    IMAGE_KEYWORDS,
    VIDEO_KEYWORDS,
)
from .models import TestResultWithTypes  # noqa: F401  (re-exported for convenience)

log = logging.getLogger(__name__)


class ProviderModelFetcher:
    """Discover providers + models, and persist them in two formats."""

    def __init__(self, base_url: str, api_key: str | None = None,
                 provider_dir: str = "provider") -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.provider_dir = provider_dir
        os.makedirs(provider_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Networking
    # ------------------------------------------------------------------
    @property
    def _headers(self) -> dict:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def _get_json(self, url: str) -> Any:
        r = requests.get(url, headers=self._headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def _list_providers(self) -> List[dict]:
        url = f"{self.base_url}/v1/providers"
        try:
            data = self._get_json(url)
            if isinstance(data, list):
                return data
            log.warning("Unexpected /v1/providers payload shape: %s", type(data).__name__)
            return []
        except requests.RequestException as e:
            log.error("Error fetching providers: %s", e)
            return []

    def _list_provider_models(self, provider_name: str) -> Tuple[List[dict], str | None]:
        """Return (models_list, error_or_none)."""
        url = f"{self.base_url}/api/{provider_name}/models"
        try:
            data = self._get_json(url)
        except requests.RequestException as e:
            return [], str(e)
        if isinstance(data, dict) and "data" in data:
            return data["data"] or [], None
        return [], None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch(self, with_types: bool = False, sleep_between: float = 0.1) -> Dict[str, Any]:
        """Fetch every provider + its models.

        When ``with_types`` is True, each model is augmented with the
        ``image`` / ``video`` / ``audio`` / ``vision`` / ``response_types``
        fields — this matches what the legacy
        ``fetch_providers_and_models_with_types`` produced.
        """
        providers = self._list_providers()
        if not providers:
            log.warning("No providers returned by %s", self.base_url)
            return {}

        provider_models: Dict[str, Any] = {}
        for provider in providers:
            name = provider.get("id", "")
            if not name:
                continue
            print(f"Fetching models for provider: {name}")
            raw_models, err = self._list_provider_models(name)

            if with_types:
                models = [self._enrich_model(m) for m in raw_models if m.get("id")]
            else:
                models = [m.get("id", "") for m in raw_models if m.get("id")]

            entry: Dict[str, Any] = {
                "provider_info": provider,
                "models": models,
                "model_count": len(models),
            }
            if err:
                entry["error"] = err
            provider_models[name] = entry
            if sleep_between:
                time.sleep(sleep_between)
        return provider_models

    # ------------------------------------------------------------------
    # Model enrichment
    # ------------------------------------------------------------------
    @staticmethod
    def _matches_any(name_lower: str, keywords: Tuple[str, ...]) -> bool:
        return any(kw in name_lower for kw in keywords)

    def _enrich_model(self, model: dict) -> dict:
        """Add response_types + normalise capability flags on a model dict."""
        image = bool(model.get("image", False))
        video = bool(model.get("video", False))
        audio = bool(model.get("audio", False))
        vision = bool(model.get("vision", False))

        name_lower = (model.get("id") or "").lower()
        image = image or self._matches_any(name_lower, IMAGE_KEYWORDS)
        video = video or self._matches_any(name_lower, VIDEO_KEYWORDS)
        audio = audio or self._matches_any(name_lower, AUDIO_KEYWORDS)

        response_types = ["text"]
        if image:
            response_types.append("image")
        if video:
            response_types.append("video")
        if audio:
            response_types.append("audio")

        return {
            "id": model.get("id", ""),
            "image": image,
            "video": video,
            "audio": audio,
            "vision": vision,
            "response_types": response_types,
        }

    @staticmethod
    def determine_response_types(model_info: dict) -> List[str]:
        """Backwards-compatible helper mirroring the legacy static method."""
        response_types = ["text"]
        if model_info.get("image", False):
            response_types.append("image")
        if model_info.get("video", False):
            response_types.append("video")
        if model_info.get("audio", False):
            response_types.append("audio")
        name_lower = (model_info.get("id") or "").lower()
        if any(kw in name_lower for kw in IMAGE_KEYWORDS) and "image" not in response_types:
            response_types.append("image")
        if any(kw in name_lower for kw in VIDEO_KEYWORDS) and "video" not in response_types:
            response_types.append("video")
        if any(kw in name_lower for kw in AUDIO_KEYWORDS) and "audio" not in response_types:
            response_types.append("audio")
        return response_types

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_to_files(self, data: Dict[str, Any], base_filename: str = "providers_models") -> None:
        """Write ``providers_models.json`` + ``providers_models.txt``."""
        json_path = os.path.join(self.provider_dir, f"{base_filename}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to {json_path}")

        txt_path = os.path.join(self.provider_dir, f"{base_filename}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("PROVIDERS AND THEIR MODELS\n")
            f.write("=" * 50 + "\n\n")
            for provider_name, provider_data in data.items():
                f.write(f"Provider: {provider_name}\n")
                f.write("-" * 30 + "\n")
                info = provider_data.get("provider_info", {})
                f.write(f"URL: {info.get('url', 'N/A')}\n")
                f.write(f"Label: {info.get('label', 'N/A')}\n")
                f.write(f"Model Count: {provider_data.get('model_count', 0)}\n")
                if "error" in provider_data:
                    f.write(f"Error: {provider_data['error']}\n")
                f.write("Models:\n")
                models = provider_data.get("models", [])
                if models:
                    for model in models:
                        f.write(f" - {model}\n")
                else:
                    f.write(" No models available\n")
                f.write("\n" + "=" * 50 + "\n\n")
        print(f"Human-readable data saved to {txt_path}")

    def create_test_format(self, data: Dict[str, Any], filename: str = "models_for_testing.txt") -> None:
        """Write the ``provider|model`` test-pairs file."""
        path = os.path.join(self.provider_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Format: provider_name|model_name\n")
            f.write("# Use this file for automated testing\n\n")
            for provider_name, provider_data in data.items():
                for model in provider_data.get("models", []):
                    f.write(f"{provider_name}|{model}\n")
        print(f"Test format saved to {path}")

    def save_with_types(self, data: Dict[str, Any]) -> None:
        """Write ``provider_models_type.json`` + ``.txt``.

        Mirrors the legacy ``save_provider_models_with_types`` so the
        optional richer report remains available if a caller opts in.
        """
        json_path = os.path.join(self.provider_dir, "provider_models_type.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Provider models with types saved to {json_path}")

        txt_path = os.path.join(self.provider_dir, "provider_models_type.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("PROVIDERS AND THEIR MODELS WITH RESPONSE TYPES\n")
            f.write("=" * 60 + "\n\n")
            for provider_name, provider_data in data.items():
                f.write(f"Provider: {provider_name}\n")
                f.write("-" * 40 + "\n")
                info = provider_data.get("provider_info", {})
                f.write(f"URL: {info.get('url', 'N/A')}\n")
                f.write(f"Label: {info.get('label', 'N/A')}\n")
                f.write(f"Model Count: {provider_data.get('model_count', 0)}\n")
                if "error" in provider_data:
                    f.write(f"Error: {provider_data['error']}\n")
                f.write("Models with Response Types:\n")
                models = provider_data.get("models", [])
                if models:
                    for model in models:
                        model_id = model.get("id", "Unknown")
                        response_types = ", ".join(model.get("response_types", ["text"]))
                        caps = []
                        if model.get("image"):
                            caps.append("Image")
                        if model.get("video"):
                            caps.append("Video")
                        if model.get("audio"):
                            caps.append("Audio")
                        if model.get("vision"):
                            caps.append("Vision")
                        f.write(f" - {model_id}\n")
                        f.write(f" Response Types: {response_types}\n")
                        if caps:
                            f.write(f" Capabilities: {', '.join(caps)}\n")
                else:
                    f.write(" No models available\n")
                f.write("\n" + "=" * 60 + "\n\n")
        print(f"Human-readable provider models with types saved to {txt_path}")

    # ------------------------------------------------------------------
    # Extraction helper
    # ------------------------------------------------------------------
    @staticmethod
    def extract_test_data(data: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Flatten the fetched dict into a list of ``(provider, model)`` pairs."""
        pairs: List[Tuple[str, str]] = []
        for provider_name, provider_data in data.items():
            for model in provider_data.get("models", []):
                # ``model`` may be either a plain string (default fetch) or
                # a dict (with_types=True) — handle both transparently.
                model_id = model if isinstance(model, str) else model.get("id")
                if model_id:
                    pairs.append((provider_name, model_id))
        return pairs

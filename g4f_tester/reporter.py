"""Persist test results in the same on-disk format as the legacy code.

Output files (all under :class:`Config.working_dir`):

* ``test_results.json`` — full structured report (summary + working + non-working).
* ``test_results.txt``  — human-readable summary.
* ``working_results.txt`` — one ``provider|model|type`` line per working entry.
* ``models.txt`` — unique ``model (type)`` lines.

These file names and contents are part of the public contract — many users
fetch them via ``raw.githubusercontent.com`` URLs, so they must not change.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Iterable, List

from .models import TestResultWithTypes

log = logging.getLogger(__name__)


class TestResultsReporter:
    """Write the four canonical result files."""

    def __init__(self, working_dir: str = "working") -> None:
        self.working_dir = working_dir
        os.makedirs(working_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _type_stats(working_results: Iterable[TestResultWithTypes]) -> dict:
        stats = {"text": 0, "image": 0, "video": 0, "audio": 0}
        for r in working_results:
            key = r.media_type or "text"
            stats[key] = stats.get(key, 0) + 1
        return stats

    @staticmethod
    def _summary(results: List[TestResultWithTypes], working: List[TestResultWithTypes],
                 non_working: List[TestResultWithTypes]) -> dict:
        avg = (sum(r.response_time for r in working) / len(working)) if working else 0
        return {
            "total_tested": len(results),
            "working_count": len(working),
            "non_working_count": len(non_working),
            "success_rate": (len(working) / len(results) * 100) if results else 0,
            "average_response_time": avg,
            "response_type_breakdown": TestResultsReporter._type_stats(working),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def save_test_results(
        self,
        results: List[TestResultWithTypes],
        base_filename: str = "test_results",
    ) -> dict:
        """Write ``test_results.json`` and ``test_results.txt``.

        Returns the summary dict so callers (e.g. main) can log it.
        """
        working = [r for r in results if r.working]
        non_working = [r for r in results if not r.working]
        summary = self._summary(results, working, non_working)

        json_data = {
            "summary": summary,
            "working_models": [
                {
                    "provider": r.provider,
                    "model": r.model,
                    "response_time": r.response_time,
                    "response_preview": r.response_content,
                    "media_type": r.media_type or "text",
                    "response_types": list(r.response_types),
                }
                for r in working
            ],
            "non_working_models": [
                {
                    "provider": r.provider,
                    "model": r.model,
                    "error": r.error,
                    "response_time": r.response_time,
                    "expected_response_types": list(r.response_types),
                }
                for r in non_working
            ],
        }

        json_path = os.path.join(self.working_dir, f"{base_filename}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        txt_path = os.path.join(self.working_dir, f"{base_filename}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("PROVIDER/MODEL TEST RESULTS WITH RESPONSE TYPES\n")
            f.write("=" * 60 + "\n\n")
            f.write("SUMMARY:\n")
            f.write(f"Total Tested: {summary['total_tested']}\n")
            f.write(f"Working: {summary['working_count']}\n")
            f.write(f"Not Working: {summary['non_working_count']}\n")
            f.write(f"Success Rate: {summary['success_rate']:.2f}%\n")
            f.write(f"Average Response Time: {summary['average_response_time']:.2f}s\n\n")
            f.write("RESPONSE TYPE BREAKDOWN:\n")
            for t, c in summary["response_type_breakdown"].items():
                f.write(f" {t.capitalize()}: {c}\n")
            f.write("\n")
            f.write("WORKING MODELS BY RESPONSE TYPE:\n")
            f.write("-" * 40 + "\n")
            for response_type in ["text", "image", "video", "audio"]:
                type_results = [r for r in working if (r.media_type or "text") == response_type]
                if not type_results:
                    continue
                f.write(f"\n{response_type.upper()} MODELS:\n")
                for r in type_results:
                    f.write(f" {r.provider}|{r.model} ({r.response_time:.2f}s)\n")
            f.write("\nNON-WORKING MODELS:\n")
            f.write("-" * 40 + "\n")
            for r in non_working:
                expected = ", ".join(r.response_types)
                f.write(f"{r.provider}|{r.model} (Expected: {expected}) - Error: {r.error}\n")

        self.save_simple_working_results(results)
        log.info("Results saved to %s and %s", json_path, txt_path)
        return summary

    def save_simple_working_results(self, results: List[TestResultWithTypes]) -> None:
        """Write ``working_results.txt`` and ``models.txt``."""
        working = [r for r in results if r.working]

        wr_path = os.path.join(self.working_dir, "working_results.txt")
        with open(wr_path, "w", encoding="utf-8") as f:
            for r in working:
                f.write(f"{r.provider}|{r.model}|{r.media_type or 'text'}\n")
        print(f"Simple working results saved to {wr_path}")

        models_path = os.path.join(self.working_dir, "models.txt")
        with open(models_path, "w", encoding="utf-8") as f:
            # Preserve insertion order while deduplicating.
            unique = list(dict.fromkeys(
                f"{r.model} ({r.media_type or 'text'})" for r in working
            ))
            for m in unique:
                f.write(f"{m}\n")
        print(f"Working models list saved to {models_path}")

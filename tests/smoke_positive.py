"""Quick positive-path test: try a known no-auth provider/model."""

import asyncio, os, sys, tempfile, shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from g4f_tester import start_g4f_api_server, cleanup_browsers
from g4f_tester.tester import ProviderModelTester
from g4f_tester.fetcher import ProviderModelFetcher


def main():
    tmp = tempfile.mkdtemp(prefix="g4f_pos_")
    try:
        print("Starting g4f API server...")
        start_g4f_api_server(port=8081, api_key="1234", poll_timeout=60)

        fetcher = ProviderModelFetcher("http://localhost:8081", "1234",
                                       provider_dir=f"{tmp}/p")
        data = fetcher.fetch(with_types=False, sleep_between=0)

        # Try to find any provider that's likely to work without auth.
        # Known no-auth providers in g4f: Blackbox, DuckDuckGo, DeepInfra, HuggingSpace, etc.
        candidates = []
        skip = {"Anthropic", "Openai", "OpenAI", "Gemini", "CopilotApp",
                "HuggingFace", "Replicate", "AzureAI", "AWS", "Cohere"}
        for prov, info in data.items():
            if prov in skip:
                continue
            for m in info.get("models", [])[:1]:  # one model per provider
                candidates.append((prov, m))
            if len(candidates) >= 5:
                break
        print(f"Candidates: {candidates}")

        tester = ProviderModelTester(
            base_url="http://localhost:8081", api_key="1234",
            max_concurrent=3, timeout=45,
            output_dir=f"{tmp}/o",
        )
        results = asyncio.run(tester.test_all_models(candidates))
        print("\nResults:")
        for r in results:
            status = "WORKING" if r.working else "FAIL"
            print(f"  [{status}] {r.provider}|{r.model} type={r.media_type} "
                  f"time={r.response_time:.2f}s err={(r.error or '')[:80]}")

        # Show any files written.
        if os.path.isdir(f"{tmp}/o"):
            print("\nOutput files:")
            for f in sorted(os.listdir(f"{tmp}/o"))[:10]:
                print(f"  {f}")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()

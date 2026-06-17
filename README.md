<div align="center">

# 🚀 g4f-working

### The daily-updated, zero-auth directory of working AI providers & models from GPT4Free

[![Daily Provider Model Testing](https://github.com/maruf009sultan/g4f-working/actions/workflows/main.yml/badge.svg)](https://github.com/maruf009sultan/g4f-working/actions/workflows/main.yml)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-green.svg?style=flat-square)](./LICENSE.md)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Updated Daily](https://img.shields.io/badge/Results-Updated%20Daily-blue.svg?style=flat-square)](#-how-it-works)
[![No API Keys](https://img.shields.io/badge/API%20Keys-NOT%20REQUIRED-brightgreen.svg?style=flat-square)](#-why-use-g4f--working)
[![Tests](https://img.shields.io/badge/Tests-76%20passing-success.svg?style=flat-square)](./tests)

</div>

> 💡 Like this project? [**⭐️ Star the repo**](https://github.com/maruf009sultan/g4f-working) to support ongoing updates and help others discover it!

---

## 📖 Table of Contents

- [🎯 What is this?](#-what-is-this)
- [✨ What's New in v2.0](#-whats-new-in-v20)
- [🚀 Quick Start](#-quick-start)
- [📂 Repository Structure](#-repository-structure)
- [⚙️ How It Works](#-how-it-works)
- [🔧 Configuration](#-configuration)
- [📦 Using as a Python Library](#-using-as-a-python-library)
- [🧪 Testing](#-testing)
- [📊 Output File Formats](#-output-file-formats)
- [🤝 Contributing](#-contributing)
- [❓ FAQ](#-faq)
- [📜 License](#-license)
- [🌐 Links](#-links)

---

## 🎯 What is this?

**g4f-working** is the ultimate, constantly-updated hub for discovering which AI providers and models from [`@xtekky/gpt4free`](https://github.com/xtekky/gpt4free) are working **right now** — and, crucially, which ones require **NO API keys, tokens or cookies**.

Skip the hassle of trial-and-error. Every day, this project:

1. 🔄 Spins up a fresh [`g4f`](https://github.com/xtekky/gpt4free) API server.
2. 🔍 Enumerates **every** provider and every model g4f knows about (typically 70+ providers, 3,000+ models).
3. 🧪 Sends a real test request to each `provider|model` pair for text, image, audio, and video capabilities.
4. 📝 Publishes the list of working ones as plain-text files you can fetch with `curl` or `wget`.

> **No Python needed. No dependencies. No API keys. Just grab the result files.**

---

## ✨ What's New in v2.0

The codebase has been refactored from a single 1,160-line file into a clean, modular Python package. **All output file names and formats are 100% backwards-compatible** — your existing automation will keep working unchanged.

### 🐛 Bugs fixed

| # | Bug | Fix |
|---|-----|-----|
| 1 | `test_video_generation` / `test_audio_generation` mutated the `payload` dict across endpoint attempts, so the second endpoint received the wrong body. | Each endpoint now builds its own fresh payload. |
| 2 | If the first endpoint returned HTTP 200 but had no media in the body, the tester gave up instead of trying the fallback endpoint. | Now `continue`s to the next endpoint before reporting failure. |
| 3 | `response_time` was measured inconsistently — sometimes from request start, sometimes from the outer try. | Uniformly measured from `start_time` at the top of each test. |
| 4 | `start_g4f_api_server` used a fixed `time.sleep(5)` to wait for readiness — flaky on slow CI. | Now polls the server's `/v1/providers` endpoint until it responds 2xx or times out. |
| 5 | `signal.signal()` was called at module import time, breaking library use. | Moved to an idempotent `install_signal_hooks()` helper that's safe to call from any thread. |
| 6 | `TestResult` dataclass was defined but never used (dead code). | Removed; only `TestResultWithTypes` is used. |
| 7 | Six duplicated `save_image_*` / `save_video_*` / `save_audio_*` methods. | Consolidated into one `MediaSaver` class with a clean public API. |
| 8 | `fetch_providers_and_models` and `fetch_providers_and_models_with_types` were near-duplicates. | Merged into one parameterised `fetch(with_types=...)` method. |
| 9 | `response_types: List[str] = None` with `__post_init__` mutation. | Replaced with `field(default_factory=lambda: ["text"])`. |
| 10 | `logging.basicConfig` was called inside `__init__` every time the class was instantiated. | Now called once in `main()`. |

### ✨ New features

- 🎛️ **Full CLI** — every setting is overridable via `--port`, `--timeout`, `--batch-size`, etc.
- 🌍 **Environment variables** — `G4F_PORT`, `G4F_API_KEY`, `G4F_TIMEOUT`, `G4F_NO_SERVER`, …
- 🔌 **Reusable as a library** — import `from g4f_tester import Config, run` and call from your own code.
- 🧪 **Comprehensive test suite** — 76 unit tests covering every module, including the bug-fixes above.
- 📦 **Modular package** — clear separation of concerns across 8 focused modules.
- 🛡️ **Safer cleanup** — `cleanup_browsers()` is now fully idempotent and never raises.

---

## 🚀 Quick Start

### For end users (just want the working list)

Nothing to install. Just fetch the raw files:

```bash
# Plain list of working models:
curl -sL https://raw.githubusercontent.com/maruf009sultan/g4f-working/refs/heads/main/working/models.txt

# Provider | Model | Type lines:
curl -sL https://raw.githubusercontent.com/maruf009sultan/g4f-working/refs/heads/main/working/working_results.txt
```

Example output:
```
Blackbox|gpt-4o-mini|text
BlackForestLabs_Flux1Dev|flux-dev|image
DuckDuckGo|gpt-4o-mini|text
HuggingSpace|command-r-08-2024|text
...
```

### For developers (want to run the tests yourself)

```bash
git clone https://github.com/maruf009sultan/g4f-working.git
cd g4f-working

# Install dependencies (system + Python)
sudo apt-get install -y ffmpeg flac          # macOS: brew install ffmpeg flac
pip install -r requirements.txt

# Run the full pipeline (starts g4f API server, fetches, tests, reports)
python provider_tester.py
```

### Common CLI overrides

```bash
# Use a different port
python provider_tester.py --port 9000

# Longer timeout for slow networks
python provider_tester.py --timeout 180

# Smaller batches to be gentle on the API
python provider_tester.py --batch-size 10 --max-concurrent 25

# Use an already-running g4f server elsewhere
python provider_tester.py --no-server --base-url http://10.0.0.5:8081

# Custom test prompts
python provider_tester.py \
  --test-message "Ping: please reply with 'pong'." \
  --image-prompt "a watercolour painting of a fox" \
  --audio-prompt "Hi, this is a TTS test."
```

---

## 📂 Repository Structure

```
g4f-working/
├── provider_tester.py         # 🚪 Entry point (thin wrapper around the g4f_tester package)
├── g4f_tester/                # 📦 The modular Python package (v2.0)
│   ├── __init__.py            #    Public API exports
│   ├── models.py              #    TestResult / TestResultWithTypes dataclasses
│   ├── config.py              #    Config dataclass + CLI arg parser + env-var loader
│   ├── server.py              #    g4f API server lifecycle + nodriver cleanup
│   ├── fetcher.py             #    ProviderModelFetcher — discovers providers & models
│   ├── tester.py              #    ProviderModelTester — probes text/image/audio/video
│   ├── media_saver.py         #    MediaSaver — saves text/image/video/audio to disk
│   ├── reporter.py            #    TestResultsReporter — writes the 4 result files
│   └── runner.py              #    Orchestration + main() + legacy facade class
├── tests/                     # 🧪 76 unit tests (no network needed)
│   ├── test_models.py
│   ├── test_config.py
│   ├── test_server.py
│   ├── test_media_saver.py
│   ├── test_fetcher.py
│   ├── test_tester.py
│   ├── test_reporter.py
│   ├── test_facade.py
│   ├── run_tests.py           #    Standalone runner (no pytest required)
│   ├── smoke_test_real.py     #    End-to-end test against a real g4f server
│   └── smoke_positive.py      #    Verifies a known-working provider succeeds
├── provider/                  # 📁 Daily output: provider/model discovery
│   ├── providers_models.json  #    Structured provider → models mapping
│   ├── providers_models.txt   #    Human-readable version of the above
│   └── models_for_testing.txt #    `provider|model` pairs (one per line)
├── working/                   # 📁 Daily output: test results
│   ├── test_results.json      #    Full structured report (summary + working + non-working)
│   ├── test_results.txt       #    Human-readable version of the above
│   ├── working_results.txt    #    `provider|model|type` for every working entry
│   └── models.txt             #    Unique `model (type)` lines
├── output/                    # 📁 Daily output: raw model responses (text/image/audio/video)
├── generated_media/           # 📁 Audio recordings from successful TTS tests
├── .github/workflows/main.yml # ⏰ GitHub Actions: runs daily at 06:00 UTC
├── requirements.txt           # 📦 Python dependencies
├── pytest.ini                 # ⚙️ Pytest configuration
├── LICENSE.md                 # 📜 CC BY-NC 4.0
└── README.md                  # 📘 You are here
```

---

## ⚙️ How It Works

```mermaid
flowchart LR
  A[g4f API server] --> B[Fetch providers]
  B --> C[Fetch models per provider]
  C --> D[For each provider|model pair]
  D --> E{Detect capabilities}
  E -->|text| F[Test chat/completions]
  E -->|image| G[Test images/generate]
  E -->|audio| H[Test audio/speech]
  E -->|video| I[Test video/generate]
  F --> J[Save response to output/]
  G --> J
  H --> J
  I --> J
  J --> K[Aggregate results]
  K --> L[Write working/ files]
  L --> M[Commit & push]
  M -->|daily 06:00 UTC| A
```

1. **Scan** — Enumerate every provider and model from `g4f`.
2. **Probe** — For each `provider|model` pair, send a tiny test request for each capability the model advertises (text, image, audio, video).
3. **Persist** — Save the raw response (text file / image / audio / video) to `/output/`.
4. **Aggregate** — Write `working_results.txt`, `models.txt`, `test_results.json`, and `test_results.txt` to `/working/`.
5. **Commit** — The GitHub Action commits the new files back to `main`.
6. **Repeat** — The cron schedule triggers again at 06:00 UTC the next day.

---

## 🔧 Configuration

Every aspect of the pipeline is configurable via **CLI flags**, **environment variables**, or **Python constructor args**. Priority: CLI > env vars > defaults.

| Setting             | CLI flag              | Env var                | Default                              |
|---------------------|-----------------------|------------------------|--------------------------------------|
| g4f API base URL    | `--base-url`          | `G4F_BASE_URL`         | `http://localhost:8081`              |
| g4f API key         | `--api-key`           | `G4F_API_KEY`          | `1234`                               |
| g4f server port     | `--port`              | `G4F_PORT`             | `8081`                               |
| Max concurrent reqs | `--max-concurrent`    | `G4F_MAX_CONCURRENT`   | `50`                                 |
| Per-request timeout | `--timeout`           | `G4F_TIMEOUT`          | `120` (seconds)                      |
| Test batch size     | `--batch-size`        | `G4F_BATCH_SIZE`       | `20`                                 |
| Provider output dir | `--provider-dir`      | —                      | `provider`                           |
| Working output dir  | `--working-dir`       | —                      | `working`                            |
| Raw output dir      | `--output-dir`        | —                      | `output`                             |
| Skip server start   | `--no-server`         | `G4F_NO_SERVER=1`      | `false` (server starts)              |
| Text test prompt    | `--test-message`      | `G4F_TEST_MESSAGE`     | `Hello, are you working? ...`        |
| Image test prompt   | `--image-prompt`      | `G4F_IMAGE_PROMPT`     | `a simple test image of a red apple` |
| Video test prompt   | `--video-prompt`      | `G4F_VIDEO_PROMPT`     | `a simple test video of a cat walking` |
| Audio test prompt   | `--audio-prompt`      | `G4F_AUDIO_PROMPT`     | `Hello, this is a test audio generation` |

Run `python provider_tester.py --help` to see all options.

---

## 📦 Using as a Python Library

The new modular design means you can reuse individual pieces in your own projects:

### Run the full pipeline programmatically

```python
import asyncio
from g4f_tester import Config, run

cfg = Config.from_env()  # reads G4F_* env vars
asyncio.run(run(cfg))
```

### Fetch the current provider/model list

```python
from g4f_tester import ProviderModelFetcher

fetcher = ProviderModelFetcher("http://localhost:8081", api_key="1234")
data = fetcher.fetch()  # → {"Blackbox": {"models": [...], ...}, ...}
```

### Test a specific provider/model

```python
import aiohttp, asyncio
from g4f_tester import ProviderModelTester

async def main():
    tester = ProviderModelTester(
        base_url="http://localhost:8081",
        api_key="1234",
        output_dir="./my_outputs",
    )
    async with aiohttp.ClientSession() as session:
        results = await tester.test_provider_model_combination(
            session, "BlackForestLabs_Flux1Dev", "flux-dev"
        )
    for r in results:
        print(f"{r.media_type}: working={r.working} time={r.response_time:.2f}s")

asyncio.run(main())
```

### Save media responses to disk

```python
import asyncio
from g4f_tester import MediaSaver

async def main():
    saver = MediaSaver("./outputs", base_url="http://localhost:8081")
    # Save from a URL:
    await saver.save_image_url("Prov", "model", "https://example.com/img.jpg")
    # Save from a base64 data URL:
    await saver.save_audio_data_url("Prov", "model", "data:audio/mp3;base64,AAAA")
    # Save raw bytes:
    await saver.save_audio_bytes("Prov", "model", b"\x00\x01\x02...")

asyncio.run(main())
```

### Backwards compatibility

Existing user scripts keep working unchanged:

```python
# This still works exactly as before:
from provider_tester import ProviderModelFetcherAndTester

tester = ProviderModelFetcherAndTester(
    "http://localhost:8081", "1234",
    max_concurrent=50, timeout=120,
)
data = tester.fetch_providers_and_models()
tester.save_to_files(data)
tester.create_test_format(data)
# ...etc
```

---

## 🧪 Testing

### Run the unit tests (no network required)

```bash
# Option A: use the standalone runner (no pytest needed)
python tests/run_tests.py

# Option B: use pytest
python -m pytest tests/ -v
```

Expected output:
```
========================================
TOTAL: 76 passed, 0 failed
========================================
```

The unit tests use mocks for the HTTP layer, so they're fast (~3 seconds) and don't need a real g4f server.

### Run the end-to-end smoke tests (requires network + g4f installed)

```bash
# Spins up a real g4f API server, fetches providers, tests 3 pairs.
python tests/smoke_test_real.py

# Finds a known-working provider and verifies it actually produces output.
python tests/smoke_positive.py
```

### What's covered

| Test file            | What it verifies                                                   |
|----------------------|--------------------------------------------------------------------|
| `test_models.py`     | Dataclass defaults, `response_types` mutation safety, `to_dict()`. |
| `test_config.py`     | CLI parser, env-var loading, dir creation, header building.        |
| `test_server.py`     | TCP-port probing, server-readiness polling, idempotent hooks.      |
| `test_media_saver.py`| Text/bytes/URL/data-URL saving, filename safety, error recovery.  |
| `test_fetcher.py`    | Provider/model discovery, JSON+TXT output formats, error handling.|
| `test_tester.py`     | Streaming responses, payload-isolation bugfix, endpoint fallback. |
| `test_reporter.py`   | All 4 output files, deduplication, empty-result handling.          |
| `test_facade.py`     | Backwards-compatible API surface for legacy users.                |

---

## 📊 Output File Formats

> ⚠️ **These formats are part of the public contract.** Many users fetch them via `raw.githubusercontent.com` URLs — do not change them without bumping the major version.

### `working/models.txt`

Plain list of working models (deduplicated), one per line, in the format `model (type)`:

```
gpt-4o-mini (text)
flux-dev (image)
tts-1 (audio)
sora-2 (video)
```

### `working/working_results.txt`

One line per working `provider|model|type` triple:

```
Blackbox|gpt-4o-mini|text
BlackForestLabs_Flux1Dev|flux-dev|image
Openai|tts-1|audio
```

### `working/test_results.json`

Structured report with summary, working models (with response previews), and non-working models (with errors). Suitable for programmatic consumption.

### `working/test_results.txt`

Human-readable summary: total tested, working count, success rate, average response time, response-type breakdown, working models grouped by type, and a list of non-working models with their errors.

### `provider/providers_models.json` + `.txt`

Full provider → models mapping. The JSON is the canonical structured form; the TXT is a pretty-printed human-readable version.

### `provider/models_for_testing.txt`

All `provider|model` pairs, one per line, prefixed by a `# Format:` comment. Used by external automation tools to know what was tested.

### `output/<Provider>_<Model>_*.{txt,jpg,mp3,mp4}`

Raw responses from each test. Filenames are constructed by replacing `/` and `\` in the model name with `_`, then appending `_response.txt`, `_image_N.jpg`, `_audio.mp3`, or `_video.mp4`.

---

## 🤝 Contributing

Pull requests, issues, and suggestions are welcome! Please:

1. 🍴 Fork the repo and create a feature branch.
2. ✅ Run `python tests/run_tests.py` before submitting — all 76 tests must pass.
3. 📝 Update the relevant section of this README if you change user-facing behaviour.
4. 🎯 Keep output file formats backwards-compatible (or bump the major version if you must break them).
5. 📜 Check [LICENSE.md](./LICENSE.md) before contributing — this project is **CC BY-NC 4.0** (non-commercial).

### Local development tips

```bash
# Run a single test file:
python tests/run_tests.py models          # tests/test_models.py

# Run with verbose pytest output:
python -m pytest tests/test_tester.py -v

# Quick syntax check on all modules:
python -c "import ast, os; [ast.parse(open(os.path.join(r,f)).read()) for r,_,fs in os.walk('g4f_tester') for f in fs if f.endswith('.py')]; print('All OK')"
```

---

## ❓ FAQ

<details>
<summary><b>Q: Do I need to run any code to use this?</b></summary>

**No!** Just fetch the result files:

```bash
curl -sL https://raw.githubusercontent.com/maruf009sultan/g4f-working/refs/heads/main/working/models.txt
```

The Python code only runs in GitHub Actions to *produce* those files.
</details>

<details>
<summary><b>Q: What does "no-auth" mean?</b></summary>

A provider/model is "no-auth" if it works **without** any of:
- API keys
- Login tokens
- Browser cookies
- OAuth credentials

We test each `provider|model` pair by sending a real request with no credentials. If it returns a valid response, it goes in the working list.
</details>

<details>
<summary><b>Q: Why do some result files contain <code>&lt;audio&gt;</code> tags?</b></summary>

Some providers return their text response with embedded media tags. For example:

```html
<audio controls src="/media/1754290396_gpt-4o-mini-audio-preview.mp3"></audio>
```

The `.txt` result file is always plain text, but it may contain HTML or markdown that links to actual media. Treat the files as plain text but expect rich media inside.
</details>

<details>
<summary><b>Q: What's the difference between <code>models.txt</code> and <code>working_results.txt</code>?</b></summary>

- **`models.txt`**: deduplicated list of model names + types (no provider info).
- **`working_results.txt`**: every working `provider|model|type` triple (provider info included, may have duplicates if multiple providers serve the same model).
</details>

<details>
<summary><b>Q: How often are results updated?</b></summary>

**Daily at 06:00 UTC**, via the GitHub Actions cron schedule in [`.github/workflows/main.yml`](./.github/workflows/main.yml). You can also trigger a run manually from the Actions tab.
</details>

<details>
<summary><b>Q: Can I use the code in my own project?</b></summary>

Yes — see [📦 Using as a Python Library](#-using-as-a-python-library) above. The package is designed to be imported and reused.

Note the license, though: **CC BY-NC 4.0** means non-commercial use only.
</details>

<details>
<summary><b>Q: I found a bug or have a feature idea. Where do I go?</b></summary>

🎉 Please [open an issue](https://github.com/maruf009sultan/g4f-working/issues) or submit a pull request. See [🤝 Contributing](#-contributing) for guidelines.
</details>

<details>
<summary><b>Q: Will my existing automation break if I upgrade to v2.0?</b></summary>

**No.** All output file names, formats, and contents are 100% backwards-compatible. The legacy `ProviderModelFetcherAndTester` class is also re-exported from `provider_tester.py`, so even scripts that `from provider_tester import ProviderModelFetcherAndTester` keep working unchanged.
</details>

---

## 📜 License

This project is licensed under **[Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/deed.en)** — see [LICENSE.md](./LICENSE.md).

In plain English:
- ✅ Share and adapt the code
- ✅ Use it for personal and academic projects
- ❌ No commercial use without permission
- ✅ Attribution required

---

## 🌐 Links

- 📦 **[@xtekky/gpt4free](https://github.com/xtekky/gpt4free)** — the upstream project this repository tests against.
- 📄 **[Latest `models.txt`](https://raw.githubusercontent.com/maruf009sultan/g4f-working/refs/heads/main/working/models.txt)** — plain list of working models.
- 📄 **[Latest `working_results.txt`](https://raw.githubusercontent.com/maruf009sultan/g4f-working/refs/heads/main/working/working_results.txt)** — `provider|model|type` triples.
- 📊 **[Latest `test_results.json`](https://raw.githubusercontent.com/maruf009sultan/g4f-working/refs/heads/main/working/test_results.json)** — full structured report.
- ⏰ **[GitHub Actions workflow](https://github.com/maruf009sultan/g4f-working/actions/workflows/main.yml)** — see the daily run history.

---

<div align="center">

### 🌟 Found this useful? [Star the repo](https://github.com/maruf009sultan/g4f-working) to help others discover it!

<sub>g4f-working — the fastest way to know which GPT4Free providers/models work right now, with NO API keys, ever.</sub>

</div>

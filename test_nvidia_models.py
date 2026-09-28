"""
Tests every promising NVIDIA NIM model with your actual API key.
Only tests models listed in the current catalog (Sept 2026).
Run: python test_nvidia_models.py

Results: OK = works, 410 = retired, 429 = rate limited, TIMEOUT = queued/slow
"""
import os, time, requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("NVIDIA_API_KEY", "").strip()
URL = "https://integrate.api.nvidia.com/v1/chat/completions"

print(f"API Key: ...{KEY[-8:]}")
print(f"Testing at: {URL}")
print()

# All models from current catalog that are chat/instruct capable
MODELS = [
    # ── DeepSeek ────────────────────────────────────────────────────────
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v4-flash-0731",
    "deepseek-ai/deepseek-v4-pro",
    # ── Meta Llama ──────────────────────────────────────────────────────
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.2-1b-instruct",
    "meta/llama-3.2-3b-instruct",
    "meta/llama-3.3-70b-instruct",
    # ── Microsoft ───────────────────────────────────────────────────────
    "microsoft/phi-4-mini-instruct",
    # ── Mistral ─────────────────────────────────────────────────────────
    "mistralai/mistral-nemotron",
    "mistralai/mixtral-8x7b-instruct",
    # ── NVIDIA own models ───────────────────────────────────────────────
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nvidia-nemotron-nano-9b-v2",
    # ── Qwen ────────────────────────────────────────────────────────────
    "qwen/qwen3-next-80b-a3b-instruct",
    # ── Others ──────────────────────────────────────────────────────────
    "moonshotai/kimi-k2-instruct",
    "stepfun-ai/step-3.5-flash",
    "z-ai/glm-5.3-flash",
    "z-ai/glm5.1",
    "minimaxai/minimax-m2.5",
]

HEADERS = {
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

PAYLOAD = {
    "messages": [{"role": "user", "content": "Say OK in one word"}],
    "max_tokens": 5,
    "temperature": 0,
}

print(f"{'MODEL':<50} {'STATUS':>7}  {'MS':>6}  RESPONSE")
print("-" * 95)

working = []
retired = []
rate_limited = []
slow = []
errors = []

for model in MODELS:
    PAYLOAD["model"] = model
    t0 = time.time()
    status = "?"
    detail = ""
    try:
        r = requests.post(URL, headers=HEADERS, json=PAYLOAD, timeout=(8, 12))
        ms = int((time.time() - t0) * 1000)
        code = r.status_code

        if code == 200:
            content = r.json()["choices"][0]["message"]["content"].strip()
            status = "✅  200"
            detail = repr(content[:30])
            working.append((model, ms))
        elif code == 410:
            status = "❌  410"
            detail = "EOL/retired"
            retired.append(model)
        elif code == 429:
            status = "⏳  429"
            detail = "rate limited"
            rate_limited.append(model)
        elif code == 403:
            status = "🔒  403"
            detail = "need paid plan"
            errors.append(model)
        else:
            status = f"❓  {code}"
            detail = r.text[:60]
            errors.append(model)

    except requests.exceptions.Timeout:
        ms = int((time.time() - t0) * 1000)
        status = "⏱️  TMO"
        detail = "queued/slow (>12s)"
        slow.append(model)
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        status = "💥  ERR"
        detail = str(e)[:50]
        errors.append(model)

    print(f"{model:<50} {status:>7}  {ms:>6}ms  {detail}")

print()
print("=" * 95)
print(f"✅ WORKING  ({len(working)}):  {[m for m,_ in working]}")
print(f"❌ RETIRED  ({len(retired)}):  {retired}")
print(f"⏱️  SLOW/TMO ({len(slow)}):  {slow}")
print(f"⏳ RATE LTD ({len(rate_limited)}):  {rate_limited}")
print(f"❓ OTHER ERR({len(errors)}):  {errors}")

if working:
    print()
    print("FASTEST WORKING MODELS:")
    for model, ms in sorted(working, key=lambda x: x[1]):
        print(f"  {ms:5d}ms  {model}")

"""
Tests the 2 models that timed out (not retired) with a longer timeout.
Also tests mistral-nemotron which got a 500 (server error, may be transient).
Run: python test_slow_models.py
"""
import os, time, requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("NVIDIA_API_KEY", "").strip()
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

MODELS = [
    ("nvidia/nemotron-3.5-lightning-30b-a3b", 60),   # 60s timeout
    ("z-ai/glm-5.3-flash",                    60),   # 60s timeout
    ("mistralai/mistral-nemotron",             30),   # 30s — was 500 error
]

print(f"Key: ...{KEY[-8:]}")
print("Testing 3 candidate models with extended timeouts...")
print()

for model, timeout_s in MODELS:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say only: OK"}],
        "max_tokens": 5,
        "temperature": 0,
    }
    print(f"Testing: {model}  (timeout={timeout_s}s)")
    t0 = time.time()
    try:
        r = requests.post(URL, headers=HEADERS, json=payload, timeout=(10, timeout_s))
        elapsed = round(time.time() - t0, 1)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"].strip()
            print(f"  ✅ WORKS! {elapsed}s  response={repr(content)}")
        else:
            print(f"  ❌ HTTP {r.status_code}  {elapsed}s")
            print(f"     {r.text[:150]}")
    except requests.exceptions.Timeout:
        elapsed = round(time.time() - t0, 1)
        print(f"  ⏱️ TIMEOUT after {elapsed}s — still in queue, not retired")
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        print(f"  💥 ERROR {elapsed}s: {str(e)[:80]}")
    print()

"""
Quick API key test — run with: python test_api.py
Tests NVIDIA and Groq keys directly, prints exact results.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

nvidia_key = os.getenv("NVIDIA_API_KEY", "")
groq_key   = os.getenv("GROQ_API_KEY",   "")

print("=" * 60)
print("KEY CHECK")
print("=" * 60)
print(f"NVIDIA key length : {len(nvidia_key)}")
print(f"NVIDIA key ends   : ...{nvidia_key[-8:]!r}")
print(f"NVIDIA has trailing space: {nvidia_key != nvidia_key.strip()}")
print(f"Groq   key length : {len(groq_key)}")
print(f"Groq   key ends   : ...{groq_key[-8:]!r}")
print()

# ── NVIDIA ────────────────────────────────────────────────────────────────
print("=" * 60)
print("NVIDIA NIM TEST")
print("=" * 60)

# Use stripped key — trailing space breaks auth
nkey = nvidia_key.strip()

nvidia_models = [
    # These should return 410 instantly:
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "moonshotai/kimi-k2-instruct",
    "qwen/qwen3-next-80b-a3b-instruct",
    # These may queue/hang:
    "mistralai/mistral-nemotron",
    "deepseek-ai/deepseek-v4-flash-0731",
]

for model in nvidia_models:
    try:
        r = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {nkey}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
            timeout=(5, 5),   # 5s hard limit — fast fail
        )
        if r.status_code == 200:
            txt = r.json()["choices"][0]["message"]["content"].strip()
            print(f"  ✅ {r.status_code}  {model}  ->  {txt[:40]!r}")
        else:
            print(f"  ❌ {r.status_code}  {model}  ->  {r.text[:100]}")
    except requests.exceptions.Timeout:
        print(f"  ⏱️ TIMEOUT  {model}")
    except Exception as e:
        print(f"  💥 ERROR    {model}  ->  {str(e)[:60]}")

print()

# ── Groq ──────────────────────────────────────────────────────────────────
print("=" * 60)
print("GROQ TEST")
print("=" * 60)

groq_models = [
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
]

for model in groq_models:
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "Say hello in one word"}], "max_tokens": 10},
            timeout=(10, 20),
        )
        if r.status_code == 200:
            txt = r.json()["choices"][0]["message"]["content"].strip()
            print(f"  ✅ {r.status_code}  {model}  ->  {txt[:40]!r}")
        else:
            print(f"  ❌ {r.status_code}  {model}  ->  {r.text[:120]}")
    except requests.exceptions.Timeout:
        print(f"  ⏱️ TIMEOUT  {model}")
    except Exception as e:
        print(f"  💥 ERROR    {model}  ->  {str(e)[:60]}")

print()
print("Done.")

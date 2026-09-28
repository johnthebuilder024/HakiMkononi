"""Test Groq key only — run: python test_groq.py"""
import os, requests
from dotenv import load_dotenv

load_dotenv()
groq_key = os.getenv("GROQ_API_KEY", "")
print(f"Groq key length: {len(groq_key)}, ends: ...{groq_key[-8:]!r}")
print()

models = [
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "llama-3.3-70b-versatile",
]

for model in models:
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Say hello in one word"}],
                "max_tokens": 10
            },
            timeout=(10, 15),
        )
        if r.status_code == 200:
            txt = r.json()["choices"][0]["message"]["content"].strip()
            print(f"OK  {r.status_code}  {model}  ->  {txt!r}")
        else:
            print(f"ERR {r.status_code}  {model}  ->  {r.text[:150]}")
    except Exception as e:
        print(f"EXC  {model}  ->  {str(e)[:80]}")

print("\nDone.")

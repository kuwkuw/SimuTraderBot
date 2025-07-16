import requests
from typing import Optional

def generate_gemini_analysis(api_key: str, prompt: str) -> Optional[str]:
    """
    Calls the Gemini API with the given prompt and returns the response text, or None on error.
    """
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}
    data = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ]
    }
    try:
        response = requests.post(url, headers=headers, params=params, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None 
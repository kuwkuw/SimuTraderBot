import google.generativeai as genai
from typing import Optional

def generate_gemini_analysis(api_key: str, prompt: str) -> Optional[str]:
    """
    Calls the Gemini API using google-generativeai with the given prompt and returns the response text, or None on error.
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip() if hasattr(response, 'text') else None
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None 
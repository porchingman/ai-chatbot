from google import genai
from app.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)


def ask_gemini(question: str) -> str:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=question
    )

    return response.text
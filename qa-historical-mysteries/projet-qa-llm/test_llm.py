import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    max_tokens=200,
    messages=[
        {"role": "user", "content": "Explique-moi en une phrase ce qu'est le RAG."}
    ]
)

print(response.choices[0].message.content)
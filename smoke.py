import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.getenv("MODEL_API_KEY")
if not api_key:
    raise SystemExit("MODEL_API_KEY missing in .env")

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=api_key)

# Step 1: list models.
models = client.models.list()
for m in models.data:
    print(m.id)

# Step 2: single Responses API call.
resp = client.responses.create(
    model="muse-spark-1.3",
    input="Reply with the single word: ok",
)
print(resp.output_text.strip())

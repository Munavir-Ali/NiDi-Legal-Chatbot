import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ.get("L2_API_KEY"))

# This will print every model your specific key is allowed to use
print("Available models for your key:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
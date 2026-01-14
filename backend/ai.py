import os
from dotenv import load_dotenv
import google.generativeai as genai
import google.api_core.exceptions
load_dotenv()

# API Key load
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("Available Models:")
for m in genai.list_models():
    print(m.name, "->", m.supported_generation_methods)

# Model (new stable name use karte hain)
model = genai.GenerativeModel("models/gemini-flash-latest")


def generate_ai_text(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except google.api_core.exceptions.ServiceUnavailable:
        return "⚠ AI service temporarily unavailable. Please try again in 1-2 minutes."
    except Exception as e:
        return f"⚠ Error: {str(e)}"

def generate_listing(product_name, category, features, template, language):
    template = template.lower().strip()

    if template == "amazon":
        prompt = f"""
        Generate content in {language}.
Create a professional Amazon product listing.

Product Name: {product_name}
Category: {category}
Features: {features}
"""
    elif template == "meesho":
        prompt = f"""
        Generate content in {language}.
Create a Meesho style product listing in simple Hinglish.

Product: {product_name}
Category: {category}
Features: {features}
"""
    elif template == "flipkart":
        prompt = f"""
        Generate content in {language}.
Create a Flipkart style product listing.

Product: {product_name}
Category: {category}
Features: {features}
"""
    else:
        prompt = f"""
        Generate content in {language}.
Create a general e-commerce product listing.

Product: {product_name}
Category: {category}
Features: {features}
"""

    result = generate_ai_text(prompt)
    return result



def generate_keywords(product):
    prompt = f"""
   
Give me SEO keywords for an e-commerce product.

Product: {product}

Generate:
1. 10 High search keywords
2. 10 Long tail keywords
3. 5 Hindi + English mix keywords
Format in clean bullet points.
"""
    response = model.generate_content(prompt)
    return response.text

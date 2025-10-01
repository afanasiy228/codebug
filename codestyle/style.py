import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === Настройки ===
INPUT_FILE = "main.cpp"
OUTPUT_FILE = "codestyle_report.txt"
MODEL = "gpt-4o-mini"

def analyze_code(code_chunk):
    prompt = f"""
    you must describe style of the code 
    do not describe a code describe only a style as compact as you can
    return kust a text ehit out numbers and more
    Code:
    ```cpp
    {code_chunk}
    ```
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    return response.choices[0].message.content.strip()


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        code = f.read()
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write((analyze_code(code)))


if __name__ == "__main__":
    main()
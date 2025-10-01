import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === Настройки ===
INPUT_FILE = "next.cpp"
OUTPUT_FILE = "codestyle_report.txt"
MODEL = "gpt-4o"  # самый дешёвый и быстрый


def restyle(code_chunk, report):
    prompt = f"""
    you must restyle code at c++ by the instructions 
    return ONLY a code nothing else WITHOUT ```cpp 
    instructios:
    ```
    {report}
    ```
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
        code1 = f.read()
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        report = f.read()
    

    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        f.write(restyle(code1, report))


if __name__ == "__main__":
    main()
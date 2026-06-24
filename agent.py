from ollama import chat
import time
import re

MODEL = "deepseek-coder:1.3b"
MAX_TOKENS = 2048
NUM_REVIEWS = 2
TEMPERATURE = .2


GENERATOR_PERSONA = """
                       You are a code generation engine.
   
                       Rules:
                       - Output only source code.
                       - Do not explain anything.
                       - Do not add comments.
                       - Do not use markdown.
                       - Do not use ``` fences.
                       - Do not add introductory text.
                       - Do not add concluding text.
                       - The output must be directly executable.
                       
                       Input: "reverse a string"
                       Output:
                       def reverse_string(s):
                           return s[::-1]
                       
                       Input: "add two numbers"
                       Output:
                       def add(a, b):
                       return a + b
                    """

REVIEWER_PERSONA =  """
                       You are a code transformation engine.
   
                       Rules:
                       - Input: Python code
                       - Output: corrected Python code only
                       - No explanations
                       - No comments
                       - No markdown
                       - No rewriting unless necessary
                       - Preserve original structure
                    """

def main():
    start = time.time()

    prompt = plan().strip() 
    if not prompt: 
        prompt = "write a factorial function"
    current = generate_code(prompt)
    for i in range(NUM_REVIEWS):
        current = review_code(current, i)


    print(f"Took {time.time() - start:.2f}s")


# functions

def plan():
    print("Hi developer how can i help you?")
    prompt = input("You: ")
    return prompt

def call_ollama(prompt, persona):
    response = chat(
        model = MODEL,
        messages = [
            { "role": "system", "content": persona },
            { "role": "user", "content": prompt },
        ],
        options = {
            "num_predict": MAX_TOKENS,   # hard limit tokens
            "temperature": TEMPERATURE
        }
    )

    return response.message.content

def generate_code(prompt):
    current = call_ollama(prompt, GENERATOR_PERSONA)

    print("=== Generation ===\n")
    print(current)

    with open("res.txt", "w") as f:
        f.write("=== Generation ===\n")
        f.write(current + "\n")
    return current

def review_code(code, i):
    current = call_ollama(
        f"""
            Review the following code.
            If there are improvements, return the improved version.
            Otherwise return the same code.
            {code}
        """,
        REVIEWER_PERSONA
    )
    # current = clean_code(current)
    print(f"\n=== Review {i + 1} ===\n")
    print(current)
    with open("res.txt", "a") as f:
        f.write(f"\n=== Review {i + 1} ===\n")
        f.write(current + "\n")
    return current

if (__name__ == "__main__"):
    main()















# def clean_code(code):
#     lines = []
#     for line in code.splitlines():
#         stripped = line.strip()

#         # remove full-line comments only
#         if stripped.startswith("#"):
#             continue

#         # remove markdown fences
#         if stripped.startswith("```"):
#             continue

#         lines.append(line)

    # return "\n".join(lines).strip()
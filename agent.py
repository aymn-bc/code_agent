from ollama import chat
import threading
import itertools
import time
import sys
import re

# MODEL = "deepseek-coder:1.3b"
MODEL = "qwen2.5-coder:1.5b"
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
                       You are a Python code improver.

                       Rules:
                       - Return only Python code.
                       - No explanations.
                       - No comments.
                       - No markdown.   
                       Input: "add two numbers"
                       Output:
                       def add(a, b):
                           return a + b   
                       Input: "add two numbers with type check"
                       Output:
                       def add(a, b):
                           if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                               raise TypeError("inputs must be numbers")
                           return a + b
                    """

def main():
    start = time.time()

    prompt = plan().strip() 
    if not prompt: 
        prompt = "write a factorial function"
    current = generate_code(prompt)
    for i in range(NUM_REVIEWS):
        current = review_code(current, i)
    current = clean_code(current)
    print("\n\n=== FINAL OUTPUT ===\n\n")
    print(current)
    print(f"Took {time.time() - start:.2f}s")


# functions

def plan():
    print("Hi developer how can i help you?")
    prompt = input("You: ")
    return prompt

def call_ollama(prompt, persona, label):
    done = False
    t = threading.Thread(target=animate, args=(label, lambda: done))
    t.start()

    response = chat(
        model = MODEL,
        messages = [
            { "role": "system", "content": persona },
            { "role": "user", "content": prompt },
        ],
        options = {
            "num_predict": MAX_TOKENS,   # hard limit tokens
            "temperature": TEMPERATURE
        },
        keep_alive=30,
    )

    done = True
    t.join()
    return response.message.content

def generate_code(prompt):
    current = call_ollama(prompt, GENERATOR_PERSONA, "Generating")

    print("=== Generation ===\n")
    # print(current)

    with open("res.txt", "w") as f:
        f.write("=== Generation ===\n")
        f.write(current + "\n")
    return current

def review_code(code, i):
    current = call_ollama(
        f"""
            Improve this Python code if possible.
            Fix bugs.
            Simplify logic.
            Return only the improved code:\n\n{code}
        """,
        REVIEWER_PERSONA,
        "Reviewing"
    )
    print(f"\n=== Review {i + 1} ===\n")
    # print(current)
    with open("res.txt", "a") as f:
        f.write(f"\n=== Review {i + 1} ===\n")
        f.write(current + "\n")
    return current

def clean_code(code):
    lines = code.splitlines()
    clean_code = []
    check = 0
    for line in lines:
        if (line.startswith("```python")):
            check = 1
            continue
        elif (line.startswith("```")):
            check = 0
        if (check == 1):
            if (line.strip().startswith("#")):
                continue
            clean_code.append(line.rstrip())

    if not clean_code:
      for line in lines:
          stripped = line.strip()
          if not stripped or stripped.startswith("#") or stripped.startswith("```"):
              continue
          clean_code.append(line.rstrip())

    return "\n".join(clean_code)

# animations
def animate(label, done_flags):
    for c in itertools.cycle(["⢿", "⣻", "⣽", "⣾", "⣷", "⣯", "⣟", "⡿"]):
        if done_flags():
            break
        sys.stdout.write(f'\r{label} ' + c)
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\r' + ' ' * 30 + '\r')


if (__name__ == "__main__"):
    main()
from ollama import chat
import subprocess
import threading
import itertools
import tempfile
import time
import sys
import re
import os

# MODEL = "deepseek-coder:1.3b"
MODEL = "qwen2.5-coder:1.5b"
MAX_TOKENS = 2048
NUM_REVIEWS = 2
TEMPERATURE = .2
MAX_RETRIES = 3
MAX_HISTORY = 20

histories = {
    "generator": [],
    "reviewer": [],
    "corrector": []
}


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
                        - Do NOT use input() or any interactive functions.
                        - Do NOT use external libraries (no pygame, no requests, etc).
                        - Use only Python standard library.
                        - Use hardcoded example values to demonstrate functionality.
                        - Always call your functions at the end of the code.

                        Input: "reverse a string"
                        Output:
                        def reverse_string(s):
                            return s[::-1]
                        print(reverse_string("hello"))

                        Input: "add two numbers"
                        Output:
                        def add(a, b):
                            return a + b
                        print(add(3, 5))
                        don't copy the example just use them as reference
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

def call_ollama(prompt, persona, agent_type, label):
    global histories

    done = False
    t = threading.Thread(target=animate, args=(label, lambda: done))
    t.start()

    # Initialiser le message système une seule fois
    if not histories[agent_type]:
        histories[agent_type].append({
            "role": "system",
            "content": persona
        })

    # Ajouter le message utilisateur
    histories[agent_type].append({
        "role": "user",
        "content": prompt
    })

    # Garder le message système + les 20 derniers messages
    if len(histories[agent_type]) > MAX_HISTORY + 1:
        histories[agent_type] = [histories[agent_type][0]] + histories[agent_type][-MAX_HISTORY:]


    response = chat(
        model = MODEL,
        messages = histories[agent_type],
        options = {
            "num_predict": MAX_TOKENS,   # hard limit tokens
            "temperature": TEMPERATURE
        },
        keep_alive=30,
    )
    code = response.message.content

    # Ajouter la réponse du modèle à l'historique
    histories[agent_type].append({
        "role": "assistant",
        "content": code
    })

    if len(histories[agent_type]) > MAX_HISTORY + 1:
        histories[agent_type] = [histories[agent_type][0]] + histories[agent_type][-MAX_HISTORY:]

    done = True
    t.join()
    return code

def generate_code(prompt):
    current = call_ollama(prompt, GENERATOR_PERSONA, "generator", "Generating")

    with open("res.txt", "w") as f:
        f.write("=== Generation ===\n")
        f.write(current + "\n")
    # print(histories["generator"])
    return evaluate(current, GENERATOR_PERSONA)

def review_code(code, i):
    current = call_ollama(
        f"""
            Improve this Python code if possible.
            Fix bugs.
            Simplify logic.
            Keep it directly executable — do not wrap in a function unless it already is one.
            Return only the improved code:\n\n{code}
        """,
        REVIEWER_PERSONA,
        "reviewer",
        "Reviewing"
    )

    with open("res.txt", "a") as f:
        f.write(f"\n=== Review {i + 1} ===\n")
        f.write(current + "\n")
        # print(histories["reviewer"])
    return evaluate(current, REVIEWER_PERSONA)

def execute(code):
    # temporary_file = "temporary.py"
    # with open(temporary_file, "w") as f:
    #     f.write(code)

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    
    try:
        result = subprocess.run(
                    [
                        "python", 
                        tmp_path
                    ],
                    stdin=subprocess.DEVNULL, # Kill input
                    capture_output=True, 
                    text=True, 
                    timeout=15
                )
        # print(result.returncode)
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, f"Execution failed:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Timeout: code took too long"
    finally:
        os.unlink(tmp_path)

def evaluate(code, persona):
    for attempt in range (MAX_RETRIES):
        cleaned = clean_code(code)
        success, output = execute(cleaned)

        if (success): 
            return cleaned
        
        code = call_ollama(
            f"This code has an error:\n\n{cleaned}\n\nError:\n{output}\n\nFix it.",
            persona,
            "corrector",
            f"Correcting {attempt + 1}"
        )
    print("\nÉchec après 3 tentatives.")
    return clean_code(code)

# optimization

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
    # execute("temporary.py")
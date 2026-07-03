from ollama import chat
import subprocess
import threading
import itertools
import tempfile
import argparse
import time
import json
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
last_code = ""


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
    args = plan()
    if (args.task):
        run_once(args.task, args)
        if (args.save):
            with open(args.save, "w") as f:
                f.write(last_code)
    elif (args.batch):
        run_batch(args.batch, args)
    else:
        run_repl(args)

    print(f"Took {time.time() - start:.2f}s")

def plan():
    parser = argparse.ArgumentParser(description = 'usage mode')
    parser.add_argument("-t", "--task", help="Task to execute")
    parser.add_argument("-s", "--save", help="Save final code to a file")
    parser.add_argument("-m","--model", help="Override the default Ollama model")
    parser.add_argument("-b",'--batch', metavar="FILE", help="Process tasks from a batch file")
    parser.add_argument( "--norun", action="store_true", help="Do not execute generated code")

    args = parser.parse_args()
    if (args.model):
        global MODEL
        MODEL = args.model
    return args

def call_ollama(prompt, persona, agent_type, label):
    global histories

    done = False
    t = threading.Thread(target=animate, args=(label, lambda: done))
    t.start()

    # initialize system message
    if not histories[agent_type]:
        histories[agent_type].append({
            "role": "system",
            "content": persona
        })

    # add user message
    histories[agent_type].append({
        "role": "user",
        "content": prompt
    })

    # save the system message + last 20 messages
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

    # add llm response to history
    histories[agent_type].append({
        "role": "assistant",
        "content": code
    })

    if len(histories[agent_type]) > MAX_HISTORY + 1:
        histories[agent_type] = [histories[agent_type][0]] + histories[agent_type][-MAX_HISTORY:]

    done = True
    t.join()
    return code

def generate_code(prompt, args):
    current = call_ollama(prompt, GENERATOR_PERSONA, "generator", "Generating")

    with open("res.txt", "w") as f:
        f.write("=== Generation ===\n")
        f.write(current + "\n")
    # print(histories["generator"])
    return evaluate(current, GENERATOR_PERSONA, args)

def review_code(code, i, args):
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
    return evaluate(current, REVIEWER_PERSONA, args)

def execute(code):
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

def evaluate(code, persona, args):
    if (not(args.norun)):
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

# mode
def run_repl(args):
    print("Hi developer how can i help you?")
    global last_code
    while(True):
        prompt = input("You: ")
        if (prompt == r"\quit"):
            print("Goodbye")
            break
        elif (prompt.startswith(r"\save")):
            parts = prompt.split()
            file_path = parts[1] if len(parts) > 1 else "output.py"
            with open(file_path, "w") as f:
                f.write(last_code)
            print(f"Saving to {file_path}")
        elif (prompt == r"\clear"):
            for key in histories:
                histories[key] = []
            print("History cleared")
        elif (prompt == r"\history"):
            show_history()
        else:
            last_code = generate_code(prompt, args)
            for i in range(NUM_REVIEWS):
                last_code = review_code(last_code, i, args)
            print("\n=== FINAL OUTPUT ===\n")
            print(clean_code(last_code))

def run_once(prompt, args):
    global last_code
    last_code = generate_code(prompt, args)
    for i in range(NUM_REVIEWS):
        last_code = review_code(last_code, i, args)
    print("\n=== FINAL OUTPUT ===\n")
    print(clean_code(last_code))

def run_batch(batch_file, args):
    global last_code
    try:
        with open(batch_file, "r") as f:
            tasks = json.load(f)
        
        report = []
        for task in tasks:
            code = generate_code(task["task"], args)
            for i in range(NUM_REVIEWS):
                code = review_code(code, i, args)
            
            if task.get("output"):
                with open(task["output"], "w") as f:
                    f.write(clean_code(code))

            report.append({
                "task": task["task"],
                "code": clean_code(code),
                "output": task.get("output", None)
            })

        with open("rapport.json", "w") as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        print("Batch done — rapport.json generated.")

    except Exception as e:
        print(f"Error: {e}")

# tools
def show_history():
    all_messages = []
    
    for agent_type, messages in histories.items():
        for msg in messages:
            if msg["role"] != "system":
                all_messages.append(f"[{agent_type}] {msg['role']}: {msg['content'][:80]}...")
    
    print("\n=== Derniers échanges ===")
    for msg in all_messages[-10:]:
        print(msg)

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
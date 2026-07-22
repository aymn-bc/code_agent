"""
Code Agent v1.1
A Python code generation agent with automatic correction.
Author: Aymen
"""


from datetime import datetime
import uuid
from ollama import chat
import subprocess
import threading
import itertools
import tempfile
import argparse
import logging
import time
import json
import sys
import os

# MODEL = "deepseek-coder:1.3b"
MODEL = "qwen2.5-coder:1.5b"
MAX_TOKENS = 2048
NUM_REVIEWS = 2
TEMPERATURE = .2
MAX_RETRIES = 3
MAX_HISTORY = 20
MIN_WORDS = 3

#BANNED_PATTERNS = [
#    "os.system", "os.remove", "os.rmdir", "os.unlink",
#    "shutil.rmtree", "subprocess", "eval(", "exec(",
#    "__import__", "socket", "urllib", "requests",
#    "sys.exit", "os.environ"
#]
PROGRAMMING_KEYWORDS = [
    "write", "create", "make", "build", "generate", "code",
    "function", "program", "script", "calculate", "sort",
    "find", "print", "parse", "convert", "give", "implement",
    "develop", "design", "fix", "reverse", "compute", "list",
    "read", "check", "validate", "format", "count", "filter"
]

histories = {
    "generator": [],
    "reviewer": [],
    "corrector": []
}
last_code = ""

PREAMBLE = """
import builtins

builtins.input = lambda *args, **kwargs: ""
"""

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

# log setup
def setup_logging():
    """Configure logging to file and console with proper formatting."""
    log_format = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    log_file = 'logs.log'
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # File handler (DEBUG level)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)-8s | %(message)s')
    console_handler.setFormatter(console_formatter)
    # Only add console handler if not in REPL mode
    # root_logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)

logger = setup_logging()

def main():
    start = time.time()
    args = plan()

    logger.info("=" * 60)
    logger.info("NEW SESSION STARTED")
    logger.info(f"Model: {MODEL} | Mode: {get_mode(args)}")
    logger.info("=" * 60)

    try:
        if (args.task):
            run_once(args.task, args)
            if (args.save):
                with open(args.save, "w") as f:
                    f.write(last_code)
                    logger.info(f"Code saved to {args.save}")
        elif (args.batch):
            run_batch(args.batch, args)
        else:
            run_repl(args)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"Error: {e}")

    passed = time.time() - start
    logger.info("=" * 60)
    logger.info(f"SESSION COMPLETED | Passed: {passed:.2f}s")
    logger.info("=" * 60)
    print(f"Took {passed:.2f}s")

def get_mode(args):
    if args.task:
        return "ONE-SHOT"
    elif args.batch:
        return "BATCH"
    else:
        return "REPL"

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
        if (model_exists(args.model)):
            MODEL = args.model
            logger.info(f"Model overridden: {MODEL}")

        else: 
            logger.error(f"Model '{args.model}' does not exist")
            print(f"Error: model '{args.model}' does not exist")
            return sys.exit(1)
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
            "content": persona,
            "datetime": datetime.now()
        })

    # add user message
    histories[agent_type].append({
        "role": "user",
        "content": prompt,
        "datetime": datetime.now()
    })

    # save the system message + last 20 messages
    if len(histories[agent_type]) > MAX_HISTORY + 1:
        histories[agent_type] = [histories[agent_type][0]] + histories[agent_type][-MAX_HISTORY:]

    logger.debug(f"[{agent_type}] Calling LLM with {len(prompt)} char prompt")
    try:
        response = chat(
        model = MODEL,
        messages = histories[agent_type],
        options = {
                "num_predict": MAX_TOKENS,   # hard limit tokens
                "temperature": TEMPERATURE
            },
            keep_alive=30,
        )
        logging.info(f"LLM is DONE")
        code = response.message.content
        logger.debug(f"[{agent_type}] LLM returned {len(code)} char response")
    except Exception as e:
        logger.error(f"[{agent_type}] LLM call failed: {e}")
        raise

    # add llm response to history
    histories[agent_type].append({
        "role": "assistant",
        "content": code,
        "datetime": datetime.now()
    })

    if len(histories[agent_type]) > MAX_HISTORY + 1:
        histories[agent_type] = [histories[agent_type][0]] + histories[agent_type][-MAX_HISTORY:]

    done = True
    t.join()
    return code

def generate_code(prompt, args):
    logging.info(f"[GENERATE] Task: {prompt[:60]}...")
    current = call_ollama(prompt, GENERATOR_PERSONA, "generator", "Generating")

    with open("res.txt", "w") as f:
        f.write("=== Generation ===\n")
        f.write(current + "\n")
    return evaluate(current, GENERATOR_PERSONA, args)

def review_code(code, i, args):
    logger.info(f"[REVIEW {i+1}] Improving code...")

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
    return evaluate(current, REVIEWER_PERSONA, args)

def execute(code):
    res, message = is_safe(code)
    remote_path = f"/tmp/{uuid.uuid4().hex}.py"
    if (res):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp:
            tmp.write(PREAMBLE + "\n" + code)
            tmp_path = tmp.name

        try:
            logger.debug(f"[EXECUTE] SCP to sandbox: {remote_path}")
            subprocess.run(["scp", '-q', tmp_path, f"sandbox:{remote_path}"], check=True)
            logger.debug(f"[EXECUTE] SSH exec: python3 {remote_path}")
            result = subprocess.run(
                        [ 
                            "ssh",
                            "sandbox",
                            "python3", 
                            remote_path
                        ],
                        stdin=subprocess.DEVNULL, # Kill input
                        capture_output=True, 
                        text=True, 
                        timeout=15
                    )
            if result.returncode == 0:
                logger.info(f"[EXECUTE] Success ✓")
                return True, result.stdout
            else:
                logger.warning(f"[EXECUTE] Failed: {result.stderr[:100]}")
                return False, f"Execution failed:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            logger.warning("[EXECUTE] Timeout: execution took >15s")
            return False, "Timeout: code took too long"
        except Exception as e:
            logger.error(f"[EXECUTE] Error: {e}")
            return False, str(e)
        finally:
            subprocess.run(["ssh", "sandbox", "rm", remote_path])
            os.unlink(tmp_path)
    else:
        return res, message


def evaluate(code, persona, args):
    if (not(args.norun)):
        logger.info("[EVALUATE] Skipped (--norun)")
        for attempt in range (MAX_RETRIES):
            cleaned = clean_code(code)
            success, output = execute(cleaned)

            if (success): 
                logger.info(f"[EVALUATE] Success on attempt {attempt + 1}/{MAX_RETRIES}")
                return cleaned, output, attempt + 1, True
            logger.warning(f"[EVALUATE] Attempt {attempt + 1} failed, retrying...")
            code = call_ollama(
                f"This code has an error:\n\n{cleaned}\n\nError:\n{output}\n\nFix it.",
                persona,
                "corrector",
                f"Correcting {attempt + 1}"
            )
        logger.error(f"[EVALUATE] Failed after {MAX_RETRIES} attempts")
        print("\nÉchec après 3 tentatives.")
        return clean_code(code), "", MAX_RETRIES, False
    return clean_code(code), "", 0, None

# mode
def run_repl(args):
    print("Hi developer how can i help you?")
    global last_code
    tools = [r"\quit", r"\save", r"\clear", r"\history", r"\help"]
    while(True):
        prompt = input("You: ")
        valid, reason = is_valid_prompt(prompt)
        if (not valid and not prompt.strip().split()[0] in tools):
            print(reason)
            continue
        if (prompt == r"\quit"):
            logger.info("[REPL] User quit")
            print("Goodbye")
            break
        elif (prompt.startswith(r"\save")):
            parts = prompt.split()
            file_path = parts[1] if len(parts) > 1 else "output.py"
            with open(file_path, "w") as f:
                f.write(last_code)
            logger.info(f"[REPL] Saved to {file_path}")
            print(f"Saving to {file_path}")
        elif (prompt == r"\clear"):
            for key in histories:
                histories[key] = []
            print("History cleared")
            logger.info("[REPL] History cleared")
        elif (prompt == r"\history"):
            show_history()
        elif prompt == r"\help":
            print(
                """
Available commands:
  \\help              Show this help message.
  \\quit              Exit the program.
  \\save [file]       Save the last generated code (default: output.py).
  \\clear             Clear the conversation history.
  \\history           Display the conversation history.  
  
Any input that does not start with '\\' is treated as a code generation prompt.
                """
                )
        else:
            logger.info(f"[REPL] Task: {prompt[:60]}")
            last_code, _, _, _ = generate_code(prompt, args)
            for i in range(NUM_REVIEWS):
                last_code, _, _, _ = review_code(last_code, i, args)
            print("\n=== FINAL OUTPUT ===\n")
            print(clean_code(last_code))

def run_once(prompt, args):
    global last_code
    valid, reason = is_valid_prompt(prompt)
    if not valid:
        logger.warning(f"[ONE-SHOT] Invalid prompt: {reason}")
        print(reason)
        return

    logger.info(f"[ONE-SHOT] Starting")
    last_code, _, _, _ = generate_code(prompt, args)
    logging.info("generator is DONE")
    for i in range(NUM_REVIEWS):
        logging.info(f"review {i+1} is RUNNING")
        last_code, _, _, _ = review_code(last_code, i, args)
        logging.info(f"review {i+1} is DONE")
    print("\n=== FINAL OUTPUT ===\n")
    print(clean_code(last_code))
    logger.info(f"[ONE-SHOT] Complete")

def run_batch(batch_file, args):
    global last_code
    logger.info(f"[BATCH] Loading {batch_file}")
    try:
        with open(batch_file, "r") as f:
            tasks = json.load(f)
        
        logger.info(f"[BATCH] Loaded {len(tasks)} tasks")
        report = []
        for i, task in enumerate(tasks, 1):

            logger.info(f"[BATCH] Task {i}/{len(tasks)}: {task['task'][:60]}")
            code, output, attempts, success = generate_code(task["task"], args)
            for i in range(NUM_REVIEWS):
                code, output, attempts, success = review_code(code, i, args)
            
            if task.get("output"):
                with open(task["output"], "w") as f:
                    f.write(clean_code(code))
                logger.info(f"[BATCH] Saved to {task['output']}")

            report.append({
                "task": task["task"],
                "code": code,
                "output": output,
                "attempts": attempts,
                "success": success
            })

        with open("rapport.json", "w") as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        logger.info(f"[BATCH] Report saved to rapport.json")
        print("Batch done — rapport.json generated.")

    except Exception as e:
        logger.error(f"[BATCH] Error: {e}")
        print(f"Error: {e}")

# tools
def show_history():
    all_messages = []

    for agent_type, messages in histories.items():
        for msg in messages:
            if msg["role"] != "system":
                all_messages.append({
                    "datetime": msg["datetime"],
                    "agent": agent_type,
                    "role": msg["role"],
                    "content": msg["content"],
                })

    all_messages.sort(key=lambda x: x["datetime"])

    print("\n=== Derniers échanges ===")
    for msg in all_messages[-10:]:
        print(
            f"[{msg['datetime']}] "
            f"[{msg['agent']}] "
            f"{msg['role']}: {msg['content'][:80]}..."
        )

def is_safe(code):
#    for pattern in BANNED_PATTERNS:
#        if pattern in code:
#            return False, f"Blocked: '{pattern}' is not allowed"
    return True, ""

def is_valid_prompt(prompt):
    if not prompt or not prompt.strip():
        return False, "Prompt cannot be empty."
    
    words = prompt.strip().split()
    if len(words) < MIN_WORDS:
        return False, f"Please be more specific (at least {MIN_WORDS} words)."
    
    if not any(kw in prompt.lower() for kw in PROGRAMMING_KEYWORDS):
        return False, "Please describe a programming task."
    
    return True, ""

def model_exists(model_name):
    try:
        models = ollama.list()
        return any(m.model == model_name for m in models.models)
    except Exception:
        return False

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
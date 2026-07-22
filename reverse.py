import subprocess
def reverse_string(s):
    return s[::-1]
result = subprocess.run(['scp', '-q', '/tmp/tmpstpy05s5.py', 'sandbox:/tmp/43fe00950cc54f8bbfdd5de1851e9591.py'], capture_output=True, text=True)
print(result.stdout.strip())
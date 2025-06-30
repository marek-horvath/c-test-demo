import re
import subprocess

def remove_main_from_c(source_path, target_path):
    with open(source_path, 'r', encoding='utf-8') as f:
        code = f.read()
    code_no_main = re.sub(
        r'int\s+main\s*\([^)]*\)\s*\{(?:[^{}]|\{[^{}]*\})*\}',
        '', code, flags=re.DOTALL)
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(code_no_main)

def compile_and_run_test(arrays_nomains_path, main_test_path, output_bin_path):
    gcc_cmd = ["gcc", main_test_path, arrays_nomains_path, "-o", output_bin_path, "-lm"]
    return subprocess.run(gcc_cmd, capture_output=True, text=True)

def run_binary(binary_path):
    return subprocess.run([binary_path], capture_output=True, text=True)

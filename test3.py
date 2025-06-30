import os
import requests
from test_helpers import remove_main_from_c, compile_and_run_test, run_binary

GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")
GITLAB_USER = os.environ.get("GITLAB_USER")
GITLAB_GROUP = "zap-problemsets/2024/e15-utorok-7.30"

MAIN_TEST_C_PATH = "/app/c-test-demo/main_test.c"  # prispôsob podľa svojho projektu

headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
api_url = f"https://git.kpi.fei.tuke.sk/api/v4/groups/{GITLAB_GROUP.replace('/', '%2F')}/projects"

results = []

def log(msg):
    print(msg)
    results.append(msg)

try:
    log(f"Querying {api_url}")
    resp = requests.get(api_url, headers=headers)
    log(f"Status code: {resp.status_code}")
    try:
        projects = resp.json()
    except Exception as e:
        log(f"API did not return JSON. Error: {str(e)}")
        log(f"API response (first 300 chars): {resp.text[:300]}")
        projects = []
except Exception as e:
    log(f"Could not contact GitLab API: {str(e)}")
    projects = []

if not isinstance(projects, list):
    log("Projects is not a list. Something went wrong with API.")
    projects = []

for project in projects:
    try:
        if not isinstance(project, dict) or 'path' not in project:
            log(f"Project is not a dict with 'path': {project}")
            continue

        repo_name = project['path']
        log("=" * 60)
        log(f"Project: {repo_name}")
        log("=" * 60)
        repo_url = f"https://{GITLAB_USER}:{GITLAB_TOKEN}@git.kpi.fei.tuke.sk/{GITLAB_GROUP}/{repo_name}.git"
        target_dir = f"./students/{repo_name}"
        os.makedirs(target_dir, exist_ok=True)

        # Klonuj
        clone_cmd = ["git", "clone", "--depth", "1", repo_url, target_dir]
        clone_proc = subprocess.run(clone_cmd, capture_output=True, text=True)
        if clone_proc.returncode != 0:
            log("Result: git clone FAILED")
            log(clone_proc.stderr.strip())
            continue

        arrays_c_path = os.path.join(target_dir, "ps2", "arrays.c")
        if not os.path.exists(arrays_c_path):
            log("Result: ps2/arrays.c NOT FOUND")
            continue

        # 1. Vyrob arrays_nomains.c
        arrays_nomains_path = os.path.join(target_dir, "ps2", "arrays_nomains.c")
        remove_main_from_c(arrays_c_path, arrays_nomains_path)

        # 2. Skompiluj main_test.c + arrays_nomains.c
        output_bin_path = os.path.join(target_dir, "ps2", "arrays_tester.out")
        gcc_proc = compile_and_run_test(arrays_nomains_path, MAIN_TEST_C_PATH, output_bin_path)
        if gcc_proc.returncode != 0:
            log("Result: COMPILATION ERROR")
            log(gcc_proc.stderr.strip())
            continue

        # 3. Spusti testovaciu binárku
        run_proc = run_binary(output_bin_path)
        if run_proc.returncode == 0:
            log("Result: OK")
            log(run_proc.stdout.strip())
        else:
            log("Result: RUNTIME ERROR")
            log(run_proc.stderr.strip())
    except Exception as e:
        log(f"Unexpected error: {str(e)}")
    finally:
        log("")  # prázdny riadok medzi projektmi

with open("result3.txt", "w", encoding="utf-8") as f:
    for line in results:
        f.write(line + "\n")

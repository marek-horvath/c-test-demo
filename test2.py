import os
import requests
import subprocess

GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")
GITLAB_USER = os.environ.get("GITLAB_USER")
GITLAB_GROUP = "zap-problemsets/2024/e15-utorok-7.30"

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
    # Pokus o JSON, ak zlyhá, vypíš response text (väčšinou HTML s chybou)
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
        log(f"Testing repo: {repo_name}")
        repo_url = f"https://{GITLAB_USER}:{GITLAB_TOKEN}@git.kpi.fei.tuke.sk/{GITLAB_GROUP}/{repo_name}.git"
        target_dir = f"./students/{repo_name}"
        os.makedirs(target_dir, exist_ok=True)

        # Klonuj
        clone_cmd = ["git", "clone", "--depth", "1", repo_url, target_dir]
        clone_proc = subprocess.run(clone_cmd, capture_output=True, text=True)
        if clone_proc.returncode != 0:
            log(f"{repo_name}: git clone FAILED: {clone_proc.stderr.strip()}")
            continue

        arrays_c_path = os.path.join(target_dir, "ps2", "arrays.c")
        if not os.path.exists(arrays_c_path):
            log(f"{repo_name}: ps2/arrays.c NOT FOUND")
            continue

        bin_path = os.path.join(target_dir, "ps2", "arrays.out")
        gcc_cmd = ["gcc", arrays_c_path, "-o", bin_path]
        gcc_proc = subprocess.run(gcc_cmd, capture_output=True, text=True)
        if gcc_proc.returncode != 0:
            log(f"{repo_name}: COMPILATION ERROR: {gcc_proc.stderr.strip()}")
            continue

        run_proc = subprocess.run([bin_path], capture_output=True, text=True)
        if run_proc.returncode == 0:
            log(f"{repo_name}: OK - output: {run_proc.stdout.strip()}")
        else:
            log(f"{repo_name}: RUNTIME ERROR: {run_proc.stderr.strip()}")
    except Exception as e:
        log(f"{project}: Unexpected error: {str(e)}")

with open("result2.txt", "w", encoding="utf-8") as f:
    for line in results:
        f.write(line + "\n")

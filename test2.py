import os
import requests
import subprocess

GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")
GITLAB_USER = os.environ.get("GITLAB_USER")
GITLAB_GROUP = "zap-problemsets/2024/e15-utorok-7.30"

headers = {
    "PRIVATE-TOKEN": GITLAB_TOKEN
}

# GitLab API endpoint
api_url = f"https://git.kpi.fei.tuke.sk/api/v4/groups/{GITLAB_GROUP.replace('/', '%2F')}/projects"

print(f"Querying {api_url}")
resp = requests.get(api_url, headers=headers)
projects = resp.json()

results = []

for project in projects:
    repo_name = project['path']
    print(f"Testing repo: {repo_name}")
    repo_url = f"https://{GITLAB_USER}:{GITLAB_TOKEN}@git.kpi.fei.tuke.sk/{GITLAB_GROUP}/{repo_name}.git"
    target_dir = f"./students/{repo_name}"
    os.makedirs(target_dir, exist_ok=True)

    # Klonuj
    clone_cmd = ["git", "clone", "--depth", "1", repo_url, target_dir]
    clone_proc = subprocess.run(clone_cmd, capture_output=True, text=True)
    if clone_proc.returncode != 0:
        results.append(f"{repo_name}: git clone FAILED: {clone_proc.stderr.strip()}")
        continue

    arrays_c_path = os.path.join(target_dir, "ps2", "arrays.c")
    if not os.path.exists(arrays_c_path):
        results.append(f"{repo_name}: ps2/arrays.c NOT FOUND")
        continue

    bin_path = os.path.join(target_dir, "ps2", "arrays.out")
    gcc_cmd = ["gcc", arrays_c_path, "-o", bin_path]
    gcc_proc = subprocess.run(gcc_cmd, capture_output=True, text=True)
    if gcc_proc.returncode != 0:
        results.append(f"{repo_name}: COMPILATION ERROR: {gcc_proc.stderr.strip()}")
        continue

    run_proc = subprocess.run([bin_path], capture_output=True, text=True)
    if run_proc.returncode == 0:
        results.append(f"{repo_name}: OK - output: {run_proc.stdout.strip()}")
    else:
        results.append(f"{repo_name}: RUNTIME ERROR: {run_proc.stderr.strip()}")

with open("result2.txt", "w", encoding="utf-8") as f:
    for line in results:
        f.write(line + "\n")

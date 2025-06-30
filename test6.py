import os
import requests
import subprocess
import importlib
import csv
from test_helpers import remove_main_from_c

# ENV premenné
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")
GITLAB_USER = os.environ.get("GITLAB_USER")
GITLAB_GROUP_ID = os.environ.get("GITLAB_GROUP_ID")   # teraz id namiesto mena
ASSIGNMENT = os.environ.get("ASSIGNMENT")      # názov assignmentu, default ps2

RESULT_FILE = "result5.txt"
CSV_FILE = "result5.csv"

# Natiahni assignment podľa mena (napr. ps2)
assignment_module = importlib.import_module(f"assignments.{ASSIGNMENT}")
TASKS = assignment_module.TASKS

headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
api_url = f"https://git.kpi.fei.tuke.sk/api/v4/groups/{GITLAB_GROUP_ID}/projects"

results = []
csv_rows = []

def log(msg):
    print(msg)
    results.append(msg)

def parse_points_from_output(output, task):
    # Hľadá TASK:nazov=1 alebo 0
    for line in output.splitlines():
        if line.startswith(f"TASK:{task}="):
            try:
                return int(line.split("=")[1])
            except Exception:
                return 0
    return 0

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

# CSV header
csv_header = ["project", "student"]
csv_header.extend([task for task, _ in TASKS])
csv_header.append("total")
csv_rows.append(csv_header)

for project in projects:
    try:
        if not isinstance(project, dict) or 'path' not in project:
            log(f"Project is not a dict with 'path': {project}")
            continue

        repo_name = project['path']
        student_name = project.get("name", "")
        log("=" * 60)
        log(f"Project: {repo_name}")
        log(f"Student: {student_name}")
        log("=" * 60)
        log("== PROJECT RAW DATA ==")
        log(str(project))
        log("=" * 22)

        repo_url = project['http_url_to_repo']
        # S tokenom a userom, kvôli autentifikácii
        if repo_url.startswith("https://"):
            repo_url = repo_url.replace("https://", f"https://{GITLAB_USER}:{GITLAB_TOKEN}@")
        target_dir = f"./students/{repo_name}"
        os.makedirs(target_dir, exist_ok=True)

        # Klonuj
        clone_cmd = ["git", "clone", "--depth", "1", repo_url, target_dir]
        clone_proc = subprocess.run(clone_cmd, capture_output=True, text=True)
        if clone_proc.returncode != 0:
            log("Result: git clone FAILED")
            for task, _ in TASKS:
                log(f"{task}: 0")
            csv_rows.append([repo_name, student_name] + [0] * len(TASKS) + [0])
            continue

        # Očakávame súbor podľa assignmentu
        arrays_c_path = os.path.join(target_dir, "ps2", "arrays.c")
        if not os.path.exists(arrays_c_path):
            log("Result: ps2/arrays.c NOT FOUND")
            for task, _ in TASKS:
                log(f"{task}: 0")
            csv_rows.append([repo_name, student_name] + [0] * len(TASKS) + [0])
            continue

        # Vyrob arrays_nomains.c
        arrays_nomains_path = os.path.join(target_dir, "ps2", "arrays_nomains.c")
        remove_main_from_c(arrays_c_path, arrays_nomains_path)

        row_points = []
        total = 0
        max_score = len(TASKS)
        for task, main_c in TASKS:
            main_test_c_path = os.path.abspath(main_c)
            output_bin_path = os.path.join(target_dir, "ps2", f"{task}_tester.out")
            gcc_cmd = ["gcc", main_test_c_path, arrays_nomains_path, "-o", output_bin_path, "-lm"]
            gcc_proc = subprocess.run(gcc_cmd, capture_output=True, text=True)

            if gcc_proc.returncode != 0:
                log(f"{task}: 0")
                row_points.append(0)
                continue

            run_proc = subprocess.run([output_bin_path], capture_output=True, text=True)
            if run_proc.returncode == 0:
                pt = parse_points_from_output(run_proc.stdout, task)
                log(f"{task}: {pt}")
                row_points.append(pt)
                total += pt
            else:
                log(f"{task}: 0")
                row_points.append(0)
        log(f"Total: {total}/{max_score}")
        csv_rows.append([repo_name, student_name] + row_points + [total])
    except Exception as e:
        log(f"Unexpected error: {str(e)}")
        for task, _ in TASKS:
            log(f"{task}: 0")
        csv_rows.append([repo_name, student_name] + [0] * len(TASKS) + [0])
    finally:
        log("")

with open(RESULT_FILE, "w", encoding="utf-8") as f:
    for line in results:
        f.write(line + "\n")

with open(CSV_FILE, "w", encoding="utf-8", newline='') as f:
    writer = csv.writer(f)
    for row in csv_rows:
        writer.writerow(row)

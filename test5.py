import os
import requests
import subprocess
import csv
from test_helpers import remove_main_from_c

GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")
GITLAB_USER = os.environ.get("GITLAB_USER")
GITLAB_GROUP_ID = os.environ.get("GITLAB_GROUP_ID")  # <-- skupinové ID

RESULT_FILE = "result3.txt"
CSV_FILE = "result3.csv"

headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}

# Používame priamo ID
api_url = f"https://git.kpi.fei.tuke.sk/api/v4/groups/{GITLAB_GROUP_ID}/projects"

TASKS = [
    ("lift_a_car", "ps2/main_test_lift_a_car.c"),
    ("unit_price", "ps2/main_test_unit_price.c"),
    ("collatz", "ps2/main_test_collatz.c"),
    ("opposite_number", "ps2/main_test_opposite_number.c"),
    ("sum_squared", "ps2/main_test_sum_squared.c"),
    ("array_max", "ps2/main_test_array_max.c"),
    ("array_min", "ps2/main_test_array_min.c"),
    ("special_counter", "ps2/main_test_special_counter.c"),
    ("special_numbers", "ps2/main_test_special_numbers.c"),
    ("counter", "ps2/main_test_counter.c"),
]

results = []
csv_rows = []

def log(msg):
    print(msg)
    results.append(msg)

def parse_points_from_output(output, task):
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

csv_header = ['project_id', 'repo_name', 'project_name'] + [task for task, _ in TASKS] + ['total']

for project in projects:
    # PRINT CELÉHO DICTIONARY projektu
    print("== PROJECT RAW DATA ==")
    print(project)
    print("======================")

    try:
        if not isinstance(project, dict) or 'path' not in project:
            log(f"Project is not a dict with 'path': {project}")
            continue

        project_id = project.get('id', '')
        repo_name = project.get('path', '')
        project_name = project.get('name', '')

        log("=" * 60)
        log(f"Project: {repo_name}")
        log("=" * 60)
        repo_url = f"https://{GITLAB_USER}:{GITLAB_TOKEN}@git.kpi.fei.tuke.sk/{repo_name}.git"
        # POZOR: ak url má byť group/repo, podľa API to môže byť project['http_url_to_repo']!
        # Bezpečnejšie:
        repo_url = project.get('http_url_to_repo')
        target_dir = f"./students/{repo_name}"
        os.makedirs(target_dir, exist_ok=True)

        # Klonuj
        clone_cmd = ["git", "clone", "--depth", "1", repo_url, target_dir]
        clone_proc = subprocess.run(clone_cmd, capture_output=True, text=True)
        if clone_proc.returncode != 0:
            log("Result: git clone FAILED")
            row = [project_id, repo_name, project_name] + [0]*len(TASKS) + [0]
            csv_rows.append(row)
            for task, _ in TASKS:
                log(f"{task}: 0")
            continue

        arrays_c_path = os.path.join(target_dir, "ps2", "arrays.c")
        if not os.path.exists(arrays_c_path):
            log("Result: ps2/arrays.c NOT FOUND")
            row = [project_id, repo_name, project_name] + [0]*len(TASKS) + [0]
            csv_rows.append(row)
            for task, _ in TASKS:
                log(f"{task}: 0")
            continue

        arrays_nomains_path = os.path.join(target_dir, "ps2", "arrays_nomains.c")
        remove_main_from_c(arrays_c_path, arrays_nomains_path)

        total = 0
        scores = []
        for task, main_c in TASKS:
            main_test_c_path = os.path.abspath(main_c)
            output_bin_path = os.path.join(target_dir, "ps2", f"{task}_tester.out")
            gcc_cmd = ["gcc", main_test_c_path, arrays_nomains_path, "-o", output_bin_path, "-lm"]
            gcc_proc = subprocess.run(gcc_cmd, capture_output=True, text=True)

            if gcc_proc.returncode != 0:
                log(f"{task}: 0")
                scores.append(0)
                continue

            run_proc = subprocess.run([output_bin_path], capture_output=True, text=True)
            if run_proc.returncode == 0:
                pt = parse_points_from_output(run_proc.stdout, task)
                log(f"{task}: {pt}")
                scores.append(pt)
                total += pt
            else:
                log(f"{task}: 0")
                scores.append(0)
        log(f"Total: {total}/{len(TASKS)}")
        row = [project_id, repo_name, project_name] + scores + [total]
        csv_rows.append(row)
    except Exception as e:
        log(f"Unexpected error: {str(e)}")
        row = [project_id, repo_name, project_name] + [0]*len(TASKS) + [0]
        csv_rows.append(row)
        for task, _ in TASKS:
            log(f"{task}: 0")
    finally:
        log("")

with open(RESULT_FILE, "w", encoding="utf-8") as f:
    for line in results:
        f.write(line + "\n")

with open(CSV_FILE, "w", encoding="utf-8", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(csv_header)
    writer.writerows(csv_rows)

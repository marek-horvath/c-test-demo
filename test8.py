import os
import requests
import subprocess
import importlib
import csv
import shutil
import time
from test_helpers import remove_main_from_c

# Debug zápis na úplný začiatok, overí, či kontajner vôbec štartuje!
with open("/results/DEBUG_START.txt", "w") as f:
    f.write("Skript sa spustil.\n")

# ENV premenné, bezpečné načítanie
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")
GITLAB_USER = os.environ.get("GITLAB_USER", "")
GITLAB_GROUP_ID = os.environ.get("GITLAB_GROUP_ID", "")
ASSIGNMENT = os.environ.get("ASSIGNMENT", "")
CONTAINER_ID = os.environ.get("CONTAINER_ID") or os.environ.get("GITLAB_GROUP_ID") or str(int(time.time()))

# Výsledné súbory majú unikátne meno pre každý beh/kontajner
CSV_FILE = f"/results/result_{CONTAINER_ID}.csv"
RESULT_FILE = f"/results/results_{CONTAINER_ID}.txt"
LOG_FILE = f"/results/logs_{CONTAINER_ID}.txt"

try:
    assignment_module = importlib.import_module(f"assignments.{ASSIGNMENT}")
    TASKS = assignment_module.TASKS
except Exception as e:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"Import error: {e}\n")
    # Zastav ďalšie spracovanie
    exit(1)

headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
BASE_API = "https://git.kpi.fei.tuke.sk/api/v4"

results_lines = []
logs_lines = []
csv_rows = []

COMPILE_TIMEOUT = 15
TEST_TIMEOUT = 20

def parse_points_from_output(output, task):
    for line in output.splitlines():
        if line.startswith(f"TASK:{task}="):
            try:
                return int(line.split("=")[1])
            except Exception:
                return 0
    return 0

def get_all_projects_recursive(group_id, path_prefix=""):
    projects = []
    subgroups_url = f"{BASE_API}/groups/{group_id}/subgroups"
    group_projects_url = f"{BASE_API}/groups/{group_id}/projects"

    r = requests.get(group_projects_url, headers=headers)
    if r.ok:
        for project in r.json():
            project['project_path'] = project.get('path_with_namespace', '')
            projects.append(project)
    r = requests.get(subgroups_url, headers=headers)
    if r.ok:
        for subgroup in r.json():
            sg_id = subgroup["id"]
            sg_path = subgroup["full_path"]
            projects += get_all_projects_recursive(sg_id, path_prefix=sg_path)
    return projects

def safe_rmtree(path):
    try:
        shutil.rmtree(path)
    except Exception:
        pass

all_projects = get_all_projects_recursive(GITLAB_GROUP_ID)

csv_header = ["project", "student", "project_path"]
csv_header.extend([task for task, _ in TASKS])
csv_header.append("total")
csv_rows.append(csv_header)

for project in all_projects:
    try:
        if not isinstance(project, dict) or 'path' not in project:
            logs_lines.append(f"{project}: not a valid dict with 'path'")
            continue

        repo_name = project['path']
        student_name = project.get("name", "")
        project_path = project.get("project_path", "")

        repo_url = project['http_url_to_repo']
        if repo_url.startswith("https://"):
            repo_url = repo_url.replace("https://", f"https://{GITLAB_USER}:{GITLAB_TOKEN}@")
        target_dir = f"./students/{repo_name}"
        safe_rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)

        clone_cmd = ["git", "clone", "--depth", "1", repo_url, target_dir]
        clone_proc = subprocess.run(clone_cmd, capture_output=True, text=True)
        if clone_proc.returncode != 0:
            logs_lines.append(f"{repo_name}: NOT SUBMITTED, git clone failed")
            continue

        arrays_c_path = os.path.join(target_dir, "ps2", "arrays.c")
        if not os.path.exists(arrays_c_path):
            logs_lines.append(f"{repo_name}: ps2/arrays.c NOT FOUND")
            continue

        arrays_nomains_path = os.path.join(target_dir, "ps2", "arrays_nomains.c")
        try:
            remove_main_from_c(arrays_c_path, arrays_nomains_path)
        except Exception as e:
            logs_lines.append(f"{repo_name}: remove_main_from_c failed: {e}")
            continue

        row_points = []
        total = 0
        successful = False
        task_errors = []
        for task, main_c in TASKS:
            main_test_c_path = os.path.abspath(main_c)
            output_bin_path = os.path.join(target_dir, "ps2", f"{task}_tester.out")
            try:
                gcc_proc = subprocess.run(
                    ["gcc", main_test_c_path, arrays_nomains_path, "-o", output_bin_path, "-lm"],
                    capture_output=True, text=True, timeout=COMPILE_TIMEOUT)
                if gcc_proc.returncode != 0:
                    task_errors.append(f"{task}: compile error")
                    row_points.append(0)
                    continue
            except subprocess.TimeoutExpired:
                task_errors.append(f"{task}: compile timeout")
                row_points.append(0)
                continue
            except Exception as e:
                task_errors.append(f"{task}: compile exception: {e}")
                row_points.append(0)
                continue

            try:
                run_proc = subprocess.run([output_bin_path], capture_output=True, text=True, timeout=TEST_TIMEOUT)
                if run_proc.returncode == 0:
                    pt = parse_points_from_output(run_proc.stdout, task)
                    row_points.append(pt)
                    total += pt
                    successful = True
                else:
                    task_errors.append(f"{task}: run fail code {run_proc.returncode}")
                    row_points.append(0)
            except subprocess.TimeoutExpired:
                task_errors.append(f"{task}: timeout")
                row_points.append(0)
            except Exception as e:
                task_errors.append(f"{task}: run exception: {e}")
                row_points.append(0)

        if successful:
            results_lines.append(f"{repo_name}: SUCCESS, total={total}, points={row_points}, path={project_path}")
            csv_rows.append([repo_name, student_name, project_path] + row_points + [total])
        else:
            logs_lines.append(f"{repo_name}: NO TASK PASSED. ERRORS: {', '.join(task_errors)}")
            csv_rows.append([repo_name, student_name, project_path] + [0] * len(TASKS) + [0])

    except Exception as e:
        logs_lines.append(f"{project.get('path', 'unknown')}: UNEXPECTED ERROR: {str(e)}")
        continue

with open(RESULT_FILE, "w", encoding="utf-8") as f:
    for line in results_lines:
        f.write(line + "\n")

with open(LOG_FILE, "w", encoding="utf-8") as f:
    for line in logs_lines:
        f.write(line + "\n")

with open(CSV_FILE, "w", encoding="utf-8", newline='') as f:
    writer = csv.writer(f)
    for row in csv_rows:
        writer.writerow(row)

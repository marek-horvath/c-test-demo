import os
import requests
import subprocess
import importlib
import csv
import shutil
import time
import sys
from test_helpers import remove_main_from_c

# ENV premenné, bezpečné načítanie
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")
GITLAB_USER = os.environ.get("GITLAB_USER", "")
GITLAB_GROUP_ID = os.environ.get("GITLAB_GROUP_ID", "")
ASSIGNMENT = os.environ.get("ASSIGNMENT", "")
CONTAINER_ID = os.environ.get("CONTAINER_ID") or os.environ.get("GITLAB_GROUP_ID") or str(int(time.time()))

CSV_FILE = f"/results/result_{CONTAINER_ID}.csv"
LOG_FILE = f"/results/logs_{CONTAINER_ID}.txt"

sys.stdout = open(LOG_FILE, "a", encoding="utf-8")
sys.stderr = sys.stdout

def print_section(title):
    print(f"\n{'='*16} {title} {'='*16}\n")

print_section("LOG STARTED")
print(f"Started: {time.ctime()}")
print(f"GITLAB_GROUP_ID={GITLAB_GROUP_ID}, ASSIGNMENT={ASSIGNMENT}")

try:
    assignment_module = importlib.import_module(f"assignments.{ASSIGNMENT}")
    TASKS = assignment_module.TASKS
    print(f"Loaded tasks: {TASKS}")
except Exception as e:
    print(f"Import error: {e}")
    exit(1)

headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
BASE_API = "https://git.kpi.fei.tuke.sk/api/v4"

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

def safe_rmtree(path):
    try:
        shutil.rmtree(path)
    except Exception as e:
        print(f"Could not rmtree {path}: {e}")

def git_clone_with_retries(clone_cmd, max_retries=5, delay_sec=7):
    for attempt in range(max_retries):
        clone_proc = subprocess.run(clone_cmd, capture_output=True, text=True)
        print(f"Clone attempt {attempt+1}: stdout: {clone_proc.stdout}")
        print(f"Clone attempt {attempt+1}: stderr: {clone_proc.stderr}")
        if clone_proc.returncode == 0:
            return True
        if "429" in clone_proc.stderr or "429" in clone_proc.stdout:
            print(f"Rate limit (429) detected, retrying in {delay_sec} seconds...")
            time.sleep(delay_sec)
        else:
            time.sleep(2)  # menšia pauza aj pri bežných erroroch
    return False

# --------- JEDNODUCHÁ NE-REKURZÍVNA VERZIA ----------
def get_group_projects(group_id):
    group_projects_url = f"{BASE_API}/groups/{group_id}/projects"
    print_section(f"GET projects for group {group_id}")
    r = requests.get(group_projects_url, headers=headers)
    if r.ok:
        return r.json()
    print(f"Failed to load projects for group {group_id}: {r.text}")
    return []

all_projects = get_group_projects(GITLAB_GROUP_ID)
print(f"Found {len(all_projects)} projects in group {GITLAB_GROUP_ID}.")

csv_header = ["project", "student", "project_path"]
csv_header.extend([task for task, _ in TASKS])
csv_header.append("total")
csv_rows = [csv_header]

for idx, project in enumerate(all_projects, 1):
    print_section(f"Processing project {idx}/{len(all_projects)}: {project.get('path', '')}")
    try:
        if not isinstance(project, dict) or 'path' not in project:
            print(f"{project}: not a valid dict with 'path'")
            continue

        repo_name = project['path']
        student_name = project.get("name", "")
        project_path = project.get("path_with_namespace", "")

        repo_url = project['http_url_to_repo']
        if repo_url.startswith("https://"):
            repo_url = repo_url.replace("https://", f"https://{GITLAB_USER}:{GITLAB_TOKEN}@")
        target_dir = f"./students/{repo_name}"
        safe_rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)

        clone_cmd = ["git", "clone", "--depth", "1", repo_url, target_dir]
        print(f"Running clone: {' '.join(clone_cmd)}")
        cloned_ok = git_clone_with_retries(clone_cmd, max_retries=7, delay_sec=7)
        if not cloned_ok:
            print(f"{repo_name}: NOT SUBMITTED, git clone failed")
            csv_rows.append([repo_name, student_name, project_path] + ["git_clone_failed"]*len(TASKS) + ["0"])
            continue

        arrays_c_path = os.path.join(target_dir, "ps2", "arrays.c")
        if not os.path.exists(arrays_c_path):
            print(f"{repo_name}: ps2/arrays.c NOT FOUND")
            csv_rows.append([repo_name, student_name, project_path] + ["arrays.c_missing"]*len(TASKS) + ["0"])
            continue

        arrays_nomains_path = os.path.join(target_dir, "ps2", "arrays_nomains.c")
        try:
            print(f"Calling remove_main_from_c: {arrays_c_path} -> {arrays_nomains_path}")
            remove_main_from_c(arrays_c_path, arrays_nomains_path)
        except Exception as e:
            print(f"{repo_name}: remove_main_from_c failed: {e}")
            csv_rows.append([repo_name, student_name, project_path] + ["remove_main_failed"]*len(TASKS) + ["0"])
            continue

        row_points = []
        total = 0
        successful = False
        task_errors = []
        for task, main_c in TASKS:
            main_test_c_path = os.path.abspath(main_c)
            output_bin_path = os.path.join(target_dir, "ps2", f"{task}_tester.out")
            try:
                print(f"Compiling for task {task}: {main_test_c_path} + {arrays_nomains_path}")
                gcc_proc = subprocess.run(
                    ["gcc", main_test_c_path, arrays_nomains_path, "-o", output_bin_path, "-lm"],
                    capture_output=True, text=True, timeout=COMPILE_TIMEOUT)
                print(f"GCC stdout: {gcc_proc.stdout}")
                print(f"GCC stderr: {gcc_proc.stderr}")
                if gcc_proc.returncode != 0:
                    print(f"{repo_name}: {task}: compile error")
                    task_errors.append(f"{task}: compile error")
                    row_points.append(0)
                    continue
            except subprocess.TimeoutExpired:
                print(f"{repo_name}: {task}: compile timeout")
                task_errors.append(f"{task}: compile timeout")
                row_points.append(0)
                continue
            except Exception as e:
                print(f"{repo_name}: {task}: compile exception: {e}")
                task_errors.append(f"{task}: compile exception: {e}")
                row_points.append(0)
                continue

            try:
                print(f"Running binary for task {task}: {output_bin_path}")
                run_proc = subprocess.run([output_bin_path], capture_output=True, text=True, timeout=TEST_TIMEOUT)
                print(f"Run stdout: {run_proc.stdout}")
                print(f"Run stderr: {run_proc.stderr}")
                if run_proc.returncode == 0:
                    pt = parse_points_from_output(run_proc.stdout, task)
                    print(f"Points parsed: {pt}")
                    row_points.append(pt)
                    total += pt
                    successful = True
                else:
                    print(f"{repo_name}: {task}: run fail code {run_proc.returncode}")
                    task_errors.append(f"{task}: run fail code {run_proc.returncode}")
                    row_points.append(0)
            except subprocess.TimeoutExpired:
                print(f"{repo_name}: {task}: timeout")
                task_errors.append(f"{task}: timeout")
                row_points.append(0)
            except Exception as e:
                print(f"{repo_name}: {task}: run exception: {e}")
                task_errors.append(f"{task}: run exception: {e}")
                row_points.append(0)

        if successful:
            print(f"{repo_name}: SUCCESS, total={total}, points={row_points}, path={project_path}")
            csv_rows.append([repo_name, student_name, project_path] + row_points + [total])
        else:
            print(f"{repo_name}: NO TASK PASSED. ERRORS: {', '.join(task_errors)}")
            csv_rows.append([repo_name, student_name, project_path] + [0] * len(TASKS) + [0])

    except Exception as e:
        print(f"{project.get('path', 'unknown')}: UNEXPECTED ERROR: {str(e)}")
        csv_rows.append([project.get('path', 'unknown'), "", "", "exception"]*len(TASKS) + ["0"])
        continue

print_section("WRITING CSV")
with open(CSV_FILE, "w", encoding="utf-8", newline='') as f:
    writer = csv.writer(f)
    for row in csv_rows:
        writer.writerow(row)

print_section("LOG ENDED")
print(f"Ended: {time.ctime()}")

# stdout sa už neuzatvára, ostáva otvorený pre docker

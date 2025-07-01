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
RESULT_FILE = f"/results/results_{CONTAINER_ID}.txt"
LOG_FILE = f"/results/logs_{CONTAINER_ID}.txt"

sys.stdout = open(LOG_FILE, "a", encoding="utf-8")
sys.stderr = sys.stdout

print(f"--- LOG STARTED {time.ctime()} ---")
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

results_lines = []
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

    print(f"GET projects for group {group_id}")
    r = requests.get(group_projects_url, headers=headers)
    if r.ok:
        for project in r.json():
            project['project_path'] = project.get('path_with_namespace', '')
            projects.append(project)
    else:
        print(f"Failed to load projects for group {group_id}: {r.text}")
    r = requests.get(subgroups_url, headers=headers)
    if r.ok:
        for subgroup in r.json():
            sg_id = subgroup["id"]
            sg_path = subgroup["full_path"]
            projects += get_all_projects_recursive(sg_id, path_prefix=sg_path)
    else:
        print(f"Failed to load subgroups for group {group_id}: {r.text}")
    return projects

def safe_rmtree(path):
    try:
        shutil.rmtree(path)
    except Exception as e:
        print(f"Could not rmtree {path}: {e}")

def git_clone_with_retries(clone_cmd, max_retries=5, delay_sec=10):
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
            break  # Other error, no sense to retry
    return False

all_projects = get_all_projects_recursive(GITLAB_GROUP_ID)
print(f"Found {len(all_projects)} projects in all subgroups.")

csv_header = ["project", "student", "project_path"]
csv_header.extend([task for task, _ in TASKS])
csv_header.append("total")
csv_rows.append(csv_header)

for project in all_projects:
    try:
        print(f"Processing project: {project}")
        if not isinstance(project, dict) or 'path' not in project:
            print(f"{project}: not a valid dict with 'path'")
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
        print(f"Running clone: {' '.join(clone_cmd)}")
        cloned_ok = git_clone_with_retries(clone_cmd, max_retries=7, delay_sec=10)
        if not cloned_ok:
            print(f"{repo_name}: NOT SUBMITTED, git clone failed")
            continue

        arrays_c_path = os.path.join(target_dir, "ps2", "arrays.c")
        if not os.path.exists(arrays_c_path):
            print(f"{repo_name}: ps2/arrays.c NOT FOUND")
            continue

        arrays_nomains_path = os.path.join(target_dir, "ps2", "arrays_nomains.c")
        try:
            print(f"Calling remove_main_from_c: {arrays_c_path} -> {arrays_nomains_path}")
            remove_main_from_c(arrays_c_path, arrays_nomains_path)
        except Exception as e:
            print(f"{repo_name}: remove_main_from_c failed: {e}")
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
        continue

print(f"Writing CSV to {CSV_FILE}")
with open(CSV_FILE, "w", encoding="utf-8", newline='') as f:
    writer = csv.writer(f)
    for row in csv_rows:
        writer.writerow(row)

print(f"Writing DONE {time.ctime()}")
print(f"--- LOG END ---")

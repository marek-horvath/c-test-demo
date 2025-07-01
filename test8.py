import os
import requests
import subprocess
import importlib
import csv
import signal
import shutil
from test_helpers import remove_main_from_c

# ENV premenné
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")
GITLAB_USER = os.environ.get("GITLAB_USER")
GITLAB_GROUP_ID = os.environ.get("GITLAB_GROUP_ID")
ASSIGNMENT = os.environ.get("ASSIGNMENT")

RESULT_FILE = "/results/result.txt"
CSV_FILE = "/results/result.csv"

assignment_module = importlib.import_module(f"assignments.{ASSIGNMENT}")
TASKS = assignment_module.TASKS

headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
BASE_API = "https://git.kpi.fei.tuke.sk/api/v4"

results = []
csv_rows = []

# Timeouty (sekundy)
COMPILE_TIMEOUT = 15
TEST_TIMEOUT = 20

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
            log(f"Project is not a dict with 'path': {project}")
            continue

        repo_name = project['path']
        student_name = project.get("name", "")
        project_path = project.get("project_path", "")

        log("=" * 60)
        log(f"Project: {repo_name}")
        log(f"Student: {student_name}")
        log(f"Project path: {project_path}")
        log("=" * 60)
        log("== PROJECT RAW DATA ==")
        log(str(project))
        log("=" * 22)

        repo_url = project['http_url_to_repo']
        if repo_url.startswith("https://"):
            repo_url = repo_url.replace("https://", f"https://{GITLAB_USER}:{GITLAB_TOKEN}@")
        target_dir = f"./students/{repo_name}"
        safe_rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)

        clone_cmd = ["git", "clone", "--depth", "1", repo_url, target_dir]
        clone_proc = subprocess.run(clone_cmd, capture_output=True, text=True)
        if clone_proc.returncode != 0:
            log("Result: git clone FAILED")
            for task, _ in TASKS:
                log(f"{task}: 0")
            csv_rows.append([repo_name, student_name, project_path] + [0] * len(TASKS) + [0])
            continue

        arrays_c_path = os.path.join(target_dir, "ps2", "arrays.c")
        if not os.path.exists(arrays_c_path):
            log("Result: ps2/arrays.c NOT FOUND")
            for task, _ in TASKS:
                log(f"{task}: 0")
            csv_rows.append([repo_name, student_name, project_path] + [0] * len(TASKS) + [0])
            continue

        arrays_nomains_path = os.path.join(target_dir, "ps2", "arrays_nomains.c")
        remove_main_from_c(arrays_c_path, arrays_nomains_path)

        row_points = []
        total = 0
        max_score = len(TASKS)
        for task, main_c in TASKS:
            main_test_c_path = os.path.abspath(main_c)
            output_bin_path = os.path.join(target_dir, "ps2", f"{task}_tester.out")
            gcc_cmd = ["gcc", main_test_c_path, arrays_nomains_path, "-o", output_bin_path, "-lm"]
            try:
                # Kompilácia s timeoutom
                gcc_proc = subprocess.run(gcc_cmd, capture_output=True, text=True, timeout=COMPILE_TIMEOUT)
                if gcc_proc.returncode != 0:
                    log(f"{task}: 0  [compile error]")
                    row_points.append(0)
                    continue
            except subprocess.TimeoutExpired:
                log(f"{task}: 0  [compile timeout]")
                row_points.append(0)
                continue
            except Exception as e:
                log(f"{task}: 0  [compile exception: {e}]")
                row_points.append(0)
                continue

            try:
                # Spustenie testu s timeoutom a catch na segfault (returncode < 0 alebo 139)
                run_proc = subprocess.run([output_bin_path], capture_output=True, text=True, timeout=TEST_TIMEOUT)
                if run_proc.returncode == 0:
                    pt = parse_points_from_output(run_proc.stdout, task)
                    log(f"{task}: {pt}")
                    row_points.append(pt)
                    total += pt
                else:
                    if run_proc.returncode < 0:
                        log(f"{task}: 0  [crashed: signal {-run_proc.returncode}]")
                    elif run_proc.returncode == 139:
                        log(f"{task}: 0  [segfault]")
                    else:
                        log(f"{task}: 0  [run fail code {run_proc.returncode}]")
                    row_points.append(0)
            except subprocess.TimeoutExpired:
                log(f"{task}: 0  [timeout >{TEST_TIMEOUT}s]")
                row_points.append(0)
            except Exception as e:
                log(f"{task}: 0  [run exception: {e}]")
                row_points.append(0)

        log(f"Total: {total}/{max_score}")
        csv_rows.append([repo_name, student_name, project_path] + row_points + [total])
    except Exception as e:
        log(f"Unexpected error: {str(e)}")
        for task, _ in TASKS:
            log(f"{task}: 0")
        csv_rows.append([repo_name, student_name, project_path] + [0] * len(TASKS) + [0])
    finally:
        log("")

with open(RESULT_FILE, "w", encoding="utf-8") as f:
    for line in results:
        f.write(line + "\n")

with open(CSV_FILE, "w", encoding="utf-8", newline='') as f:
    writer = csv.writer(f)
    for row in csv_rows:
        writer.writerow(row)

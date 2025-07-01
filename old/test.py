import subprocess
import os

# Predpokladáme, že main je v priečinku ../c-student-demo
student_bin = "../c-student-demo/main"
if not os.path.exists(student_bin):
    print("main nenájdený")
else:
    result = subprocess.run([student_bin], capture_output=True, text=True)
    print("STDOUT:", result.stdout)
    print("Return code:", result.returncode)

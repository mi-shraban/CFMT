import os.path, json, subprocess, re, requests, stat, time
from fileinput import filename

USER_CONFIG_FILE = "user_config.json"
CONTEST_QUEUE_FILE = "contest_queue.json"


# input sanitation
def get_valid_prob_id():
    while True:
        probId = input('Problem ID: (eg. 2160B): ').strip()
        if not probId:
            print("Problem ID mustn't be empty.")
            continue
        if not re.match(r'^[0-9]+[A-Z][1-9]*$', probId):
            print("This doesn't look like a valid problem ID.")
            continue
        return probId


def get_valid_user_name():
    while True:
        username = input("Github username: ").strip()
        if not username:
            print("Github username mustn't be empty.")
            continue
        if len(username) > 39:
            print("Provided string too long, cannot be Github username.")
            continue
        if not re.match(r"^[a-z\d](?:[a-z\d-]{0,37}[a-z\d])?$", username):
            print("This doesn't look like a valid Github username.")
            continue
        return username


def get_valid_repo_name():
    while True:
        reponame = input("Repository name: ").strip()
        if not reponame:
            print("Repository name mustn't be empty.")
            continue
        if reponame.endswith(".git"):
            return reponame.rstrip(".git")
        if len(reponame) > 100:
            print("Provided string too long, cannot be Repository name.")
            continue
        if not re.match("^[A-Za-z0-9._-]{1,100}$", reponame):
            print("This doesn't look like a valid Repository name.")
            continue
        return reponame


def get_valid_cf_username():
    while True:
        handle = input("Codeforces handle: ").strip()
        if not handle:
            print("Codeforces username mustn't be empty.")
            continue
        data = requests.get(f"https://codeforces.com/api/user.info?handles={handle}&checkHistoricHandles=False").json()
        if data["status"] == 'OK':
            return handle
        else:
            print("Codeforces username wasn't found. Recheck spelling")
            continue


def load_user_config():
    if not os.path.isfile(USER_CONFIG_FILE):
        return None
    with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user_config(cfg):
    with open(USER_CONFIG_FILE, 'w', encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)


def validate_user_config(cfg):
    required_keys = ("github_username", "git_repo_name", "cf_username")
    if not isinstance(cfg, dict):
        return False
    return all(k in cfg and isinstance(cfg[k], str) for k in required_keys)


def create_user():
    print("Set up a repository for your Codeforces solutions if you haven't.")

    github_username = get_valid_user_name()
    git_repo_name = get_valid_repo_name()
    cf_username = get_valid_cf_username()

    if not is_git_logged_in():
        print(f"--- To access Git push operation: \n"
              f"--- Download and Log into Github Desktop app from: "
              f"'https://desktop.github.com/download/'\n"
              f"--- Otherwise, your solutions will be stored in {git_repo_name}, "
              f"you can push the changes later on."
        )

    user_config = {
        "github_username": github_username,
        "git_repo_name": git_repo_name,
        "cf_username": cf_username,
    }
    save_user_config(user_config)

    if os.path.exists(git_repo_name) and os.path.isdir(git_repo_name):
        print(f"{git_repo_name} folder exists in directory, skipping the cloning.")
    else:
        os.system(f'git clone https://github.com/{github_username}/{git_repo_name}.git')


def open_code_file_with_template(l, p):
    if not os.path.isfile(p):
        with open(f'{l}_template.txt', 'r') as template, open(p, 'w') as cf_file:
            cf_file.write(template.read())


def compile_code(l, p):
    if l == 'cpp':
        exe_name = "a.exe" if os.name == "nt" else "a.out"
        res = subprocess.run(["g++", "-std=c++17", "-O2", p, "-o", exe_name], capture_output=True, text=True)
        if res.returncode == 0:
            print('Compiled Successfully')
            if res.stderr.strip():
                print(f"[Compiler Warnings]:\n{res.stderr.strip()}")
        else:
            print('Compilation Failed:')
            print(res.stderr.strip())
    elif l == 'py':
        print('Compilation not needed.')


def run_code(l, p):
    print('input here:')
    if l == 'cpp':
        exe_name = "a.exe" if os.name == "nt" else "./a.out"
        subprocess.run([exe_name])
        print()
    elif l == 'py':
        subprocess.run([sys.executable, p])


def is_git_logged_in():
    name = subprocess.getoutput("git config --global user.name").strip()
    email = subprocess.getoutput("git config --global user.email").strip()
    return bool(name) and bool(email)


def load_queue():
    if not os.path.isfile(CONTEST_QUEUE_FILE):
        return {}
    with open(CONTEST_QUEUE_FILE, 'r', encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue):
    with open(CONTEST_QUEUE_FILE, 'w', encoding="utf-8") as f:
        json.dump(queue, f, indent=4)


def contest_time_solve(handle, pId, f):
    try:
        submission_list = requests.get(
            f"https://codeforces.com/api/user.status?"
            f"handle={handle}&from={1}&count={15}",
            timeout=10
        ).json()

        contest_list = requests.get(
            "https://codeforces.com/api/contest.list?gym=false",
            timeout=10
        ).json()

        queue = load_queue()

        if submission_list.get('status') != 'OK' or contest_list.get('status') != 'OK':
            return False

        for s in submission_list.get('result', []):
            contestId = f"{s.get('problem', {}).get('contestId', '')}"
            problemId = f"{contestId}{s.get('problem', {}).get('index', '')}"
            if problemId == pId and (s.get('verdict') in ('OK', 'PARTIAL')) and s.get('author', {}).get('participantType') == "CONTESTANT":
                for c in contest_list.get('result', []):
                    if f"{c.get('id')}" == contestId:
                        contest_end = c.get('startTimeSeconds', 0) + c.get('durationSeconds', 0)
                        if f not in queue:
                            queue[f] = contest_end
                            save_queue(queue)
                        return True
        return False
    except Exception as e:
        print(f"Error checking contest status: {e}")
        return False


def git_push(f, cf_handle, pId):
    if not contest_time_solve(cf_handle, pId, f):
        print(f"Adding {f} to Git...")
        subprocess.run(["git", "add", f], cwd=solve_folder)
        subprocess.run(["git", "commit", "-m", f"solved {pId}"], cwd=solve_folder)

        print("Pulling latest changes...")
        subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=solve_folder)

        print("Pushing to GitHub...")
        subprocess.run(["git", "push", "origin", "main"], cwd=solve_folder)
    else:
        print(f"Added {f} to Contest Queue.\n"
              f"Queued solutions will be auto pushed to Github on Restart after contest is finished.\n")


def git_push_queue():
    curr_time = int(time.time())
    queue = load_queue()
    if not queue:
        return

    ready = []
    pending = {}
    for fname, contest_end in queue.items():
        if curr_time >= contest_end:
            ready.append(fname)
        else:
            pending[fname] = contest_end

    if not ready:
        return

    prob_names = [prob.split('.')[0] for prob in ready]
    print(f"Adding {', '.join(prob_names)} from contest queue to Git...")

    subprocess.run(["git", "add"] + ready, cwd=solve_folder)
    commit_msg = f"solved contest problems {', '.join(prob_names)}"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=solve_folder)
    subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=solve_folder)
    subprocess.run(["git", "push", "origin", "main"], cwd=solve_folder)
    print(f"{', '.join(prob_names)} pushed to Github.")

    save_queue(pending)


curr_dir = os.path.dirname(os.path.abspath(__file__))

user_config = load_user_config()
if user_config is None:
    create_user()
    user_config = load_user_config()

solve_folder = user_config["git_repo_name"]
cf_handle = user_config["cf_username"]

directory = os.path.join(os.getcwd(), f'{solve_folder}/')
if not os.path.exists(directory):
    os.makedirs(directory)

git_push_queue()

probId = get_valid_prob_id()
lang = input("Enter language extension: (eg: 'cpp'/'py'): ")
file = f"{probId}.{lang}"
path = os.path.join(directory, f"{file}")
open_code_file_with_template(lang, path)

os.system(f"code {path}")
print("\nTry for no more than 30 minutes...(Check tutorial to understand)\n")

while True:
    if is_git_logged_in():
        print("\t-'c' to compile code (C++) \n\t-'r' to run code \n\t-'g' for git push \n\t-'q' to quit\n")
    else:
        print("\t-'c' to compile code (C++) \n\t-'r' to run code \n\t-'q' to quit\n")
    try:
        x = input("Option: ")
        if x.lower() == 'c':
            compile_code(lang, path)
        if x.lower() == 'r':
            run_code(lang, path)
        if x.lower() == 'g':
            git_push(file, cf_handle, probId)
        if x.lower() == 'q':
            print("quitting...\n")
            break
    except Exception as e:
        print(e)
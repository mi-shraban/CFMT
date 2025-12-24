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
    if l == 'py':
        if not os.path.isfile(p):
            with open('py_template.txt', 'r') as template, open(p, 'w') as cf_file:
                cf_file.write(template.read())
    elif l == 'cpp':
        if not os.path.isfile(p):
            with open('cpp_template.txt', 'r') as template, open(p, 'w') as cf_file:
                cf_file.write(template.read())


def compile_code(l, p):
    if l == 'cpp':
        os.system(f'g++ -std=c++14 {p}')
        print('Compiled Successfully')
    elif l == 'py':
        print('Compilation not needed.')


def run_code(l, p):
    print('input here:')
    if l == 'cpp':
        os.system('a')
        print()
    elif l == 'py':
        os.system(f"python {p}")


def is_git_logged_in():
    name = subprocess.getoutput("git config --global user.name").strip()
    email = subprocess.getoutput("git config --global user.email").strip()
    return bool(name) and bool(email)


def load_queue():
    if not os.path.isfile(CONTEST_QUEUE_FILE):
        return []
    with open(CONTEST_QUEUE_FILE, 'r', encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue):
    with open(CONTEST_QUEUE_FILE, 'w', encoding="utf-8") as f:
        json.dump(queue, f, indent=4)


def contest_time_solve(handle, pId, f):
    l, r = 1, 10

    data = requests.get(
        f"https://codeforces.com/api/user.status?"
        f"handle={handle}&from={l}&count={r}"
    ).json()

    curr_time = time.time()
    queue = load_queue()

    for s in data['result']:
        problemId = f"{s['problem']['contestId']}{s['problem']['index']}"
        if (
            problemId != pId
            or s['verdict'] != 'OK'
            or s['author']['participantType'] != "CONTESTANT"
        ):
            continue

        contest_id = f"{s['problem']['contestId']}"
        contest_start = curr_time - s["relativeTimeSeconds"]

        contest = None
        for c in queue:
            if c['contestId'] == contest_id and c['pending']:
                contest = c
                break

        if contest is None:
            contest_length = int(input("Enter Contest length (in Hours, eg.: 2): "))
            contest = {
                'pending': True,
                'contestId': contest_id,
                'contestStart': contest_start,
                'contestLength': contest_length,
                'solved': {}
            }
            queue.append(contest)

        if problemId not in contest['solved']:
            contest['solved'][problemId] = f
            save_queue(queue)
        return True
    return False


def git_push(f, cf_handle, pId):
    if not contest_time_solve(cf_handle, pId, f):
        print(f"Adding {f} to Git")
        os.chdir("cf_solves")
        os.system(f"git add {f}")
        os.system(f'git commit -m "solved {pId}"')

        print("Pulling latest changes...")
        os.system("git pull --rebase --autostash")

        print("Pushing to GitHub...")
        os.system(f"git push origin main")
        os.chdir("..")
    else:
        print(f"Added {f} to Contest Queue.\nPlease push to GitHub after contest is finished.\n")


def git_push_queue():
    curr_time = int(time.time())
    updated = False
    queue = load_queue()
    if not queue:
        return

    for contest in queue:
        if not contest['pending']:
            continue

        contest_start = queue['contestStart']
        contest_length = queue['contestLength'] * 60 * 60
        contest_end = contest_start + contest_length

        if curr_time < contest_end:
            return

        solved_files = list(contest['solved'].values())

        print(f"Adding {' '.join(solved_files)} from contest queue to Git")
        os.chdir("cf_solves")
        os.system(f"git add {' '.join(solved_files)}")
        os.system(f'git commit -m "solved contest problems {" ".join(solved_files)}"')
        os.system("git pull --rebase --autostash")
        os.system("git push origin main")
        os.chdir("..")

        queue['pending'] = False
        updated = True
        print(f"{' '.join(queue)} pushed to Github")

    if updated:
        save_queue(queue)


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
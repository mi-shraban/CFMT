import os.path, subprocess, re, requests, stat, time


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


def create_user():
    print("Set up a repository for your Codeforces solutions if you haven't.")
    github_username = get_valid_user_name()
    git_repo_name = get_valid_repo_name()
    cf_username = get_valid_cf_username()
    if not is_git_logged_in():
        print(f"--- To access Git push operation: \n"
              f"--- Download and Log into Github Desktop app from: "
              f"'https://desktop.github.com/download/'\n"
              f"--- Otherwise, your solutions will be stored in {solve_folder}, "
              f"you can push the changes later on.")
    with open("user_info.txt", "w") as f:
        f.write(f"{git_repo_name}\n")
        f.write(f"{cf_username}\n")
    try:
        # windows
        if os.name == 'nt':
            os.chmod("user_info.txt", stat.S_IREAD)
        # linux/mac
        else:
            os.chmod("user_info.txt", stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    except Exception as e:
        print(f"Failed to make file read only: {e}")
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


def contest_time_solve(handle, pId, f):
    l, r = 1, 500
    data = requests.get(f"https://codeforces.com/api/user.status?handle={handle}&from={l}&count={r}").json()
    curr_time = time.time()
    for s in data['result']:
        probId = f"{s['problem']['contestId']}{s['problem']['index']}"
        verdict = s['verdict']
        partType = s['author']['participantType']
        subTime = s["creationTimeSeconds"]

        if probId == pId and verdict == "OK":
            # 8760 hrs in a year
            if partType == "CONTESTANT" and curr_time - subTime < 3 * 60 * 60:
                with open("contest_queue.txt", "a") as cq:
                    cq.write(f"{f} {subTime}\n")
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


curr_dir = os.path.dirname(os.path.abspath(__file__))
user_info = os.path.join(curr_dir, "user_info.txt")

if not os.path.isfile(user_info):
    create_user()

with open("user_info.txt", "r") as f:
    solve_folder = f.readline().strip()
    cf_handle = f.readline().strip()

directory = os.path.join(os.getcwd(), f'{solve_folder}/')
if not os.path.exists(directory):
    os.makedirs(directory)


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
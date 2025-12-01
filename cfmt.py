import os.path


def create_user():
    print("Set up a repository for your Codeforces solutions if you haven't.")
    github_username = input("Github username: ")
    git_repo_name = input("Repository name: ")
    with open("user_info.txt", "w") as f:
        f.write(f"{git_repo_name}")
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
    elif lang == 'py':
        print('Compilation not needed.')


def run_code(l, p):
    print('input here:')
    if l == 'cpp':
        os.system('a')
        print()
    elif l == 'py':
        os.system(f"python {p}")


def git_push(f, pId):
    print(f"Adding {f} to Git")
    os.chdir("cf_solves")
    os.system(f"git add {f}")
    os.system(f'git commit -m "solved {pId}"')

    print("Pulling latest changes...")
    os.system("git pull --rebase --autostash")

    print("Pushing to GitHub...")
    os.system(f"git push origin main")
    os.chdir("..")


curr_dir = os.path.dirname(os.path.abspath(__file__))
user_info = os.path.join(curr_dir, "user_info.txt")

if not os.path.isfile(user_info):
    create_user()

with open("user_info.txt", "r") as f:
    solve_folder = f.read().strip()

directory = os.path.join(os.getcwd(), f'{solve_folder}/')
if not os.path.exists(directory):
    os.makedirs(directory)

probId = input('Problem ID: (eg. 2160B): ')
lang = input("Enter language extension: (eg: 'cpp'/'py'): ")
file = probId + '.py'
path = os.path.join(directory, f"{file}")
open_code_file_with_template(lang, path)


os.system(f"code {path}")
print("\nTry for no more than 30 minutes...(Check tutorial to understand)\n")

while True:
    print("\t-'c' to compile code (C++) \n\t-'r' to run code \n\t-'g' for git push \n\t-and 'q' to quit\n")
    try:
        x = input("Option: ")
        if x.lower() == 'c':
            compile_code(lang, path)
        if x.lower() == 'r':
            run_code(lang, path)
        if x.lower() == 'g':
            git_push(file, probId)
        if x.lower() == 'q':
            print("quitting...\n")
            break
    except Exception as e:
        print(e)

import os.path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--id', dest='id', required=True, type=str, help='problemID. eg: 2167B')
args = parser.parse_args()

directory = os.path.join(os.getcwd(), 'cf_solves/')
if not os.path.exists(directory):
    os.makedirs(directory)

print("Sure!! Let's go! You got 20 minutes...\n")

lang = input('Input language extension: eg: .cpp, .py etc.\n')

if lang == 'py':
    path = os.path.join(directory, f"{args.id}.py")
    if not os.path.isfile(path):
        with open('py_template.txt', 'r') as template, open(path, 'w') as cf_file:
            cf_file.write(template.read())
elif lang == 'cpp':
    path = os.path.join(directory, f"{args.id}.cpp")
    if not os.path.isfile(path):
        with open('cpp_template.txt', 'r') as template, open(path, 'w') as cf_file:
            cf_file.write(template.read())


os.system(f"code {path}")
os.system(f"timeout -t 1200")

while True:
    try:
        x = input("'r'+'enter' to run code, 'q'+'enter' to quit...\n")
        if x == 'r':
            print('input here:\n')
            os.system(f"python {path}")
            print("\ncool...'r'+'enter' to run again.\n")
        elif x == 'q':
            print("quitting...\n")
            break
    except Exception as e:
        print(e)

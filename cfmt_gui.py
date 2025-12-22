import sys, os, subprocess, threading, re, stat, requests, time
import tkinter as tk
from tkinter import messagebox, simpledialog
import ttkbootstrap as ttk
from ttkbootstrap.widgets.scrolled import ScrolledText


class UserInfoDialog(tk.Toplevel):
	def __init__(self, parent):
		super().__init__(parent)
		self.title("CF Repo Setup")
		self.geometry("450x300")
		self.resizable(False, False)
		try:
			self.iconbitmap("codeforces.ico")
		except Exception as e:
			pass

		ttk.Label(self, text="GitHub Username:", font=("Segoe UI", 11)).pack(pady=10)
		self.username_entry = ttk.Entry(self, width=40)
		self.username_entry.pack()

		ttk.Label(self, text="CF Repository Name:", font=("Segoe UI", 11)).pack(pady=10)
		self.repo_entry = ttk.Entry(self, width=40)
		self.repo_entry.pack()

		ttk.Label(self, text="CF Username:", font=("Segoe UI", 11)).pack(pady=10)
		self.cf_handle_entry = ttk.Entry(self, width=40)
		self.cf_handle_entry.pack()

		ttk.Button(self, text="OK", command=self.submit).pack(pady=15)

		self.username = None
		self.repo = None
		self.cf_handle = None
		self.grab_set()

	@staticmethod
	def validate_username(username):
		if not username:
			return False, "Github username mustn't be empty."
		if len(username) > 39:
			return False, "Provided string too long, cannot be Github username."
		if not re.match(r"^[a-z\d](?:[a-z\d-]{0,37}[a-z\d])?$", username):
			return False, "This doesn't look like a valid Github username."
		return True, ""

	@staticmethod
	def validate_repo_name(reponame):
		if not reponame:
			return False, "Repository name mustn't be empty."
		# Remove .git suffix if present
		if reponame.endswith(".git"):
			reponame = reponame.rstrip(".git")
		if len(reponame) > 100:
			return False, "Provided string too long, cannot be Repository name."
		if not re.match(r"^[A-Za-z0-9._-]{1,100}$", reponame):
			return False, "This doesn't look like a valid Repository name."
		return True, reponame

	@staticmethod
	def validate_cf_handle(cf_handle):
		if not cf_handle:
			return False, "Coderforces handle mustn't be empty."
		data = requests.get(f"https://codeforces.com/api/user.info?handles={cf_handle}&checkHistoricHandles=False").json()
		if data["status"] == 'OK':
			return True, ""
		else:
			return False, "Codeforces username wasn't found. Recheck spelling"

	def submit(self):
		username = self.username_entry.get().strip()
		repo = self.repo_entry.get().strip()
		cf_handle = self.cf_handle_entry.get().strip()
		# Validate username
		is_valid, error_msg = self.validate_username(username)
		if not is_valid:
			messagebox.showwarning("Invalid Username", error_msg)
			return
		# Validate repository name
		is_valid, reponame = self.validate_repo_name(repo)
		if not is_valid:
			messagebox.showwarning("Invalid Repository Name", reponame)
			return
		is_valid, error_msg = self.validate_cf_handle(cf_handle)
		if not is_valid:
			messagebox.showwarning("Invalid CF Handle", error_msg)
			return

		if os.path.exists(reponame) and os.path.isdir(reponame):
			use_existing = messagebox.askyesno(
				"Repository Already Cloned",
				f"{reponame} already exists and is not an empty directory.\n"
				f"Yes: Use existing repo.\n"
				f"No: Enter a different repo\n"
			)
			if use_existing:
				self.username = username
				self.repo = reponame
				self.cf_handle = cf_handle
				self.destroy()
				return
			else:
				return

		clone_res = os.system(f"git clone https://github.com/{username}/{reponame}.git")
		if clone_res:
			retry = messagebox.askretrycancel("Repository Not Found\n",
								f"Failed to clone github.com/{username}{reponame}\n"
								f"-- Check if the Repository exists.\n"
								f"-- Recheck the spellings\n"
								f"-- Check internet connection\n")
			if retry:
				return
			else:
				sys.exit(1)
		self.username = username
		self.repo = reponame
		self.cf_handle = cf_handle
		self.destroy()


class GitPushThread(threading.Thread):
	def __init__(self, file_path, prob_id, solve_folder, cf_handle, output_callback, finished_callback):
		super().__init__(daemon=True)
		self.file_path = file_path
		self.prob_id = prob_id
		self.solve_folder = solve_folder
		self.cf_handle = cf_handle
		self.output_callback = output_callback
		self.finished_callback = finished_callback

	def contest_time_solve(self):
		try:
			l, r = 1, 8
			data = requests.get(f"https://codeforces.com/api/user.status?handle={self.cf_handle}&from={l}&count={r}").json()

			curr_time = time.time()
			file_name = os.path.basename(self.file_path)

			for s in data['result']:
				probId = f"{s['problem']['contestId']}{s['problem']['index']}"
				verdict = s['verdict']
				partType = s['author']['participantType']
				subTime = s["creationTimeSeconds"]

				if probId == self.prob_id and verdict == 'OK':
					# 8760 hrs in a year
					if partType == 'CONTESTANT' and curr_time - subTime < 3 * 60 * 60:
						with open("contest_queue.txt", "a") as cq:
							cq.write(f"{file_name} {subTime}\n")
						return True
			return False
		except Exception as e:
			self.output_callback(f"Error checking contest time: {e}\n")
			return False

	def run(self):
		try:
			if self.contest_time_solve():
				self.output_callback(
					f"Added {os.path.basename(self.file_path)} to Contest Queue, due to it being a Contest Solution.\n"
					f"Eligible to be pushed to GitHub in 3 hours from submission.\n"
					f"Will be pushed to Github when you run CFMT after 3 hours or later.\n"
				)
				self.finished_callback()
				return

			# Normal git push flow
			os.chdir(self.solve_folder)

			self.output_callback(f"Adding {os.path.basename(self.file_path)}...\n")
			os.system(f"git add {os.path.basename(self.file_path)}")

			self.output_callback(f"Committing solved {self.prob_id}...\n")
			os.system(f'git commit -m "solved {self.prob_id}"')

			self.output_callback("Pulling latest changes...\n")
			os.system("git pull --rebase --autostash")

			self.output_callback("Pushing to GitHub...\n")
			os.system("git push origin main")

			os.chdir("..")
			self.output_callback("Completed.\n\n\n")
		except Exception as e:
			self.output_callback(f"Error: {str(e)}\n")
		finally:
			self.finished_callback()


class CFMT_GUI:
	def __init__(self, root, folder, cf_handle):
		self.root = root
		self.current_file_path = None
		self.current_lang = tk.StringVar(value='py')
		self.git_thread = None

		self.solve_folder = folder
		self.cf_handle = cf_handle

		self.available_themes = [
			'litera', 'flatly', 'minty', 'sandstone', 'morph',
			'solar', 'superhero', 'darkly', 'cyborg', 'vapor'
		]
		# 5 light themes, 5 dark themes
		self.init_ui()
		self.root.after(500, self.git_push_queue)

	def init_ui(self):
		self.root.title("CFMT - Codeforces Management Tool")
		self.root.geometry("1440x720")

		self.root.iconbitmap("codeforces.ico")

		# Main container
		main_frame = ttk.Frame(self.root, padding="20")
		main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(0, weight=1)
		main_frame.columnconfigure(0, weight=1)

		# Header with theme button
		header_frame = ttk.Frame(main_frame)
		header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
		header_frame.columnconfigure(0, weight=1)

		header = ttk.Label(header_frame, text="Codeforces Management Tool",
						   font=("Segoe UI", 24, "bold"))
		header.grid(row=0, column=0, sticky=tk.W)

		self.theme_btn = ttk.Menubutton(header_frame,
										text=f"{self.root.style.theme.name.capitalize()}",
										bootstyle="info-outline")
		self.theme_btn.grid(row=0, column=1, sticky=tk.E, padx=(10, 5))

		theme_menu = tk.Menu(self.theme_btn, tearoff=0)
		self.theme_btn["menu"] = theme_menu

		for theme in self.available_themes:
			theme_menu.add_command(label=theme.capitalize(),
								   command=lambda t=theme: self.change_theme(t))

		# Problem Input
		prob_frame = ttk.Frame(main_frame)
		prob_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
		prob_frame.columnconfigure(1, weight=1)

		ttk.Label(prob_frame,
				  text="Problem ID:",
				  font=("Segoe UI", 11, "bold")).grid(row=0,
													  column=0,
													  padx=(0, 10))

		self.prob_input = ttk.Entry(prob_frame, font=("Segoe UI", 10))
		self.prob_input.insert(0, "e.g., 2160B")
		self.prob_input.bind("<FocusIn>", lambda e: self.prob_input.delete(0, tk.END)
							if self.prob_input.get() == "e.g., 2160B" else None)
		self.prob_input.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

		# Language selection
		lang_frame = ttk.Frame(main_frame)
		lang_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)

		ttk.Label(lang_frame,
				  text="Language:",
				  font=("Segoe UI", 11, "bold")).grid(row=0,
													  column=0,
													  padx=(0, 10))

		ttk.Radiobutton(lang_frame,
						text="Python",
						variable=self.current_lang,
						value="py").grid(row=0,
										 column=1,
										 padx=5)
		ttk.Radiobutton(lang_frame,
						text="C++",
						variable=self.current_lang,
						value="cpp").grid(row=0,
										  column=2,
										  padx=5)

		# Create file button
		self.create_btn = ttk.Button(main_frame,
									 text="Create Code File",
									 command=self.create_file)
		self.create_btn.grid(row=3, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

		# Action buttons
		actions_frame = ttk.Frame(main_frame)
		actions_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
		actions_frame.columnconfigure([0, 1, 2], weight=1)

		self.compile_btn = ttk.Button(actions_frame,
									  text="Compile (C++)",
									  command=self.compile_code,
									  state="disabled")
		self.compile_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)

		self.run_btn = ttk.Button(actions_frame,
								  text="Run Code",
								  command=self.run_code,
								  state="disabled")
		self.run_btn.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

		self.git_btn = ttk.Button(actions_frame,
								  text="Git Push",
								  command=self.git_push,
								  state="disabled")
		self.git_btn.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=5)

		# Bottom section with logs and input
		bottom_frame = ttk.Frame(main_frame)
		bottom_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
		bottom_frame.columnconfigure([0, 1], weight=1)
		main_frame.rowconfigure(5, weight=1)

		# Left: Logs & Outputs
		left_frame = ttk.Frame(bottom_frame)
		left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 5))
		left_frame.rowconfigure(1, weight=1)
		left_frame.columnconfigure(0, weight=1)

		ttk.Label(left_frame,
				  text="Logs & Outputs:",
				  font=("Segoe UI", 11, "bold")).grid(row=0,
													  column=0,
													  sticky=tk.W,
													  pady=(0, 5))

		self.log_text = ScrolledText(left_frame,
									 wrap=tk.WORD,
									 font=("Consolas", 10),
									 autohide=True)
		self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
		self.log_text.text.config(state="disabled")

		# Right: Inputs
		right_frame = ttk.Frame(bottom_frame)
		right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 5))
		right_frame.rowconfigure(1, weight=1)
		right_frame.columnconfigure(0, weight=1)
		bottom_frame.rowconfigure(0, weight=1)

		ttk.Label(right_frame,
				  text="Input Box:",
				  font=("Segoe UI", 11, "bold")).grid(row=0,
													  column=0,
													  sticky=tk.W,
													  pady=(0, 5))

		self.input_box = ScrolledText(right_frame, wrap=tk.WORD,
									  font=("Consolas", 10),
									  autohide=True)
		self.input_box.insert("1.0", "Paste test input here BEFORE RUNNING THE CODE...")
		self.input_box.bind("<FocusIn>", self.clear_input_placeholder)
		self.input_box.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

	def change_theme(self, theme_name):
		"""Change the application theme and save it as default"""
		self.root.style.theme_use(theme_name)

		# Update button text to show current theme
		self.theme_btn.config(text=f"{theme_name.capitalize()}")

		# Save theme preference
		try:
			with open("theme_preference.txt", "w") as f:
				f.write(theme_name)
			if hasattr(self, 'log_text'):
				self.append_log(f"--- Theme changed to {theme_name.capitalize()}\n")
		except Exception as e:
			messagebox.showerror("Error", f"Could not save theme preference: {e}")

	def clear_input_placeholder(self, event):
		if self.input_box.get("1.0", tk.END).strip() == "Paste test input here BEFORE RUNNING THE CODE...":
			self.input_box.delete("1.0", tk.END)

	def append_log(self, text):
		self.log_text.text.config(state="normal")
		self.log_text.text.insert(tk.END, text)
		self.log_text.text.see(tk.END)
		self.log_text.text.config(state="disabled")

	@staticmethod
	def validate_problem_id(prob_id):
		"""Validate problem ID format (e.g., 2160B)"""
		if not prob_id:
			return False, "Problem ID mustn't be empty."
		if not re.match(r'^[0-9]+[A-Z][1-9]*$', prob_id):
			return False, "This doesn't look like a valid problem ID."
		return True, ""

	def create_file(self):
		prob_id = self.prob_input.get().strip()

		is_valid, error_msg = self.validate_problem_id(prob_id)
		if not is_valid or prob_id == "e.g., 2160B":
			messagebox.showwarning("Invalid Input", error_msg or "Enter a valid Problem ID!")
			return

		ext = self.current_lang.get()
		file_name = f"{prob_id}.{ext}"
		file_path = os.path.join(self.solve_folder, file_name)

		# From template
		if not os.path.exists(file_path):
			template = f"{ext}_template.txt"
			if os.path.exists(template):
				with open(template, "r") as t, open(file_path, "w") as cf:
					cf.write(t.read())
			else:
				open(file_path, "w").close()

		self.current_file_path = file_path
		if os.name == "nt":
			subprocess.Popen(f'code "{file_path}"',
							 shell=True,
							 creationflags=subprocess.CREATE_NO_WINDOW)
		else:
			subprocess.Popen(f'code "{file_path}"', shell=True)

		self.input_box.delete("1.0", tk.END)
		self.input_box.insert("1.0", "Paste test input here BEFORE RUNNING THE CODE...")
		self.append_log(f"--- {file_name} created ---\n")

		self.compile_btn.config(state="normal")
		self.run_btn.config(state="normal")
		self.git_btn.config(state="normal")

		if not self.is_git_logged_in():
			self.append_log(f"--- To access Git push operation: \n"
							f"--- Download and Log into Github Desktop app from: "
							f"'https://desktop.github.com/download/'\n"
							f"--- Otherwise, your solutions will be stored in {self.solve_folder}, "
							f"you can push the changes later on.\n")
			self.git_btn.config(state="disabled")

	def compile_code(self):
		if self.current_lang.get() == "py":
			self.append_log("Python does not need compilation.\n")
			return

		cmd = f'g++ -std=c++14 "{self.current_file_path}" -o a.exe'
		self.append_log(f"\nCompiling...\n")
		result = os.system(cmd)
		if result == 0:
			self.append_log("\nCompiled successfully!\n")
		else:
			self.append_log("\nCompilation failed!\n")

	def run_code(self):
		prob_id = self.prob_input.get().strip()
		if not prob_id or prob_id == "e.g., 2160B":
			messagebox.showwarning("Error", "Enter a Problem ID first!")
			return

		self.append_log(f"--- Running {prob_id} ---\n")
		user_input = self.input_box.get("1.0", tk.END)

		if user_input.strip() == "Paste test input here BEFORE RUNNING THE CODE...":
			user_input = ""

		try:
			if self.current_lang.get() == "cpp":
				cmd = ["a.exe"]
			elif self.current_lang.get() == "py":
				cmd = ["python", self.current_file_path]

			# Proper way to run code with stdin/stdout pipes
			process = subprocess.Popen(
				cmd,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				text=True
			)

			stdout, stderr = process.communicate(user_input)

			# Display program output
			if stdout.strip():
				self.append_log("-- Output:\n")
				self.append_log(stdout + "\n")

			if stderr.strip():
				self.append_log("\n[Error]\n" + stderr + "\n")

		except Exception as e:
			self.append_log(f"\nRuntime Error: {str(e)}\n")

	@staticmethod
	def is_git_logged_in():
		name = subprocess.getoutput("git config --global user.name").strip()
		email = subprocess.getoutput("git config --global user.email").strip()
		return bool(name) and bool(email)

	def git_push(self):
		prob_id = self.prob_input.get().strip()

		self.git_btn.config(state="disabled")
		self.append_log("\n--- Git Push Started ---\n")

		def on_finished():
			self.root.after(0, lambda: self.git_btn.config(state="normal"))

		def on_output(text):
			self.root.after(0, lambda: self.append_log(text))

		self.git_thread = GitPushThread(
			self.current_file_path,
			prob_id,
			self.solve_folder,
			self.cf_handle,
			on_output,
			on_finished
		)
		self.git_thread.start()

	def git_push_queue(self):
		if not os.path.isfile("contest_queue.txt"):
			return
		with open("contest_queue.txt", "r") as contest_queue:
			file = [x.strip() for x in contest_queue]
		queue = set()
		rem_queue = set()
		curr_time = time.time()
		for x in file:
			fname, subtime = x.split(' ')
			if curr_time - int(subtime) > 3 * 60 * 60:
				queue.add(fname)
			else:
				rem_queue.add(f"{x}\n")
		if rem_queue:
			with open("contest_queue.txt", "w") as contest_queue:
				contest_queue.writelines(rem_queue)
		else:
			with open("contest_queue.txt", "w") as contest_queue:
				contest_queue.write("")
		if queue:
			self.append_log(f"--- Pushing from Contest Queue ---\n")
			os.chdir(self.solve_folder)

			self.append_log(f"Adding files: {', '.join(queue)}\n")
			os.system(f"git add {' '.join(queue)}")

			self.append_log(f"Committing 'solved contest problems {' '.join(queue)}'\n")
			os.system(f'git commit -m "solved contest problems {" ".join(queue)}"')

			self.append_log("Pulling latest changes...\n")
			os.system("git pull --rebase --autostash")

			self.append_log("Pushing to GitHub...\n")
			os.system("git push origin main")
			os.chdir("..")

			self.append_log(f"{', '.join(queue)} pushed to Github\n")
		if rem_queue:
			self.append_log(f"--- Contest Queue Updated ---\n")
		else:
			self.append_log(f"--- Contest Queue Cleared ---\n")


def main():
	# Load saved theme
	default_theme = "darkly"
	if os.path.exists("theme_preference.txt"):
		try:
			with open("theme_preference.txt", "r") as f:
				saved_theme = f.read().strip()
				if saved_theme:
					default_theme = saved_theme
		except:
			pass

	# Create root FIRST (hidden)
	root = ttk.Window(themename=default_theme)
	root.withdraw()   # << Hide the main window

	if not os.path.exists("user_info.txt"):
		dialog = UserInfoDialog(root)
		root.wait_window(dialog)

		github_username = dialog.username
		git_repo_name = dialog.repo
		cf_handle = dialog.cf_handle

		if not github_username or not git_repo_name:
			messagebox.showerror("Error", "Both fields are required.")
			sys.exit(1)

		with open("user_info.txt", "w") as f:
			f.write(git_repo_name+'\n')
			f.write(cf_handle+'\n')
		try:
			# windows ;-;
			if os.name == 'nt':
				os.chmod("user_info.txt", stat.S_IREAD)
			# linux/mac
			else:
				os.chmod("user_info.txt", stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
		except Exception as e:
			print(f"Failed to make file read only: {e}")
	else:
		with open("user_info.txt", "r") as f:
			git_repo_name = f.readline().strip()
			cf_handle = f.readline().strip()

	# Now show the main GUI
	root.deiconify()
	app = CFMT_GUI(root, git_repo_name, cf_handle)
	root.mainloop()


if __name__ == "__main__":
	main()

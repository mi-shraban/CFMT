import sys, os, subprocess, threading, re, stat, requests, time, json
import tkinter as tk
from tkinter import messagebox, simpledialog
import ttkbootstrap as ttk
from ttkbootstrap.widgets.scrolled import ScrolledText

USER_CONFIG_FILE = "user_config.json"
CONTEST_QUEUE_FILE = "contest_queue.json"


def load_user_config():
	if not os.path.isfile(USER_CONFIG_FILE):
		return None
	with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
		return json.load(f)


def save_user_config(cfg):
	with open(USER_CONFIG_FILE, "w", encoding="utf-8") as f:
		json.dump(cfg, f, indent=4)


def validate_user_config(cfg):
	required_keys = ("github_username", "git_repo_name", "cf_username")
	if not isinstance(cfg, dict):
		return False
	return all(k in cfg and isinstance(cfg[k], str) for k in required_keys)


def load_queue():
	if not os.path.isfile(CONTEST_QUEUE_FILE):
		return {}
	with open(CONTEST_QUEUE_FILE, "r", encoding="utf-8") as f:
		return json.load(f)


def save_queue(cfg):
	with open(CONTEST_QUEUE_FILE, "w", encoding="utf-8") as f:
		json.dump(cfg, f, indent=4)


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
		data = requests.get(
			f"https://codeforces.com/api/user.info?handles={cf_handle}&checkHistoricHandles=False").json()
		if data["status"] == 'OK':
			return True, ""
		else:
			return False, "Codeforces username wasn't found. Recheck spelling"

	def submit(self):
		username = self.username_entry.get().strip()
		repo = self.repo_entry.get().strip()
		cf_handle = self.cf_handle_entry.get().strip()

		is_valid, error_msg = self.validate_username(username)
		if not is_valid:
			messagebox.showwarning("Invalid Username", error_msg)
			return

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
			submission_list = requests.get(
				f"https://codeforces.com/api/user.status?"
				f"handle={self.cf_handle}&from={1}&count={15}"
			).json()
			contest_list = requests.get(
				"https://codeforces.com/api/contest.list?gym=false"
			).json()

			queue = load_queue()
			file_name = os.path.basename(self.file_path)

			for s in submission_list['result']:
				contestId = f"{s['problem']['contestId']}"
				problemId = f"{contestId}{s['problem']['index']}"
				if problemId == self.prob_id and (s['verdict'] == 'OK' or s['verdict'] == 'PARTIAL') and s['author'][
					'participantType'] == "CONTESTANT":
					for c in contest_list['result']:
						if f"{c['id']}" == contestId:
							contest_end = c['startTimeSeconds'] + c['durationSeconds']
							if file_name not in queue:
								queue[file_name] = contest_end
								save_queue(queue)
							return True
				else:
					continue
			return False
		except Exception as e:
			self.output_callback(f"Error checking contest time: {e}\n")
			return False

	def run(self):
		try:
			if self.contest_time_solve():
				self.output_callback(
					f"Added {os.path.basename(self.file_path)} to Contest Queue, due to it being a Contest Solution.\n"
					f"Queued solutions will be auto pushed to Github on Restart after contest is finished."
				)
				self.finished_callback(close_tab=True)
				return

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
			self.finished_callback(close_tab=True)
		except Exception as e:
			self.output_callback(f"Error: {str(e)}\n")
			self.finished_callback(close_tab=False)


class GitPushQueueThread(threading.Thread):
	def __init__(self, solve_folder, output_callback):
		super().__init__(daemon=True)
		self.solve_folder = solve_folder
		self.output_callback = output_callback

	def run(self):
		curr_time = int(time.time())
		try:
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

			self.output_callback(f"--- Pushing from Contest Queue ---\n")
			os.chdir(self.solve_folder)

			self.output_callback(f"Adding {', '.join(prob.split('.')[0] for prob in ready)} "
								 f"from contest queue to Git\n")
			os.system(f"git add {' '.join(ready)}")

			self.output_callback(f"Committing 'solved contest problems "
								 f"{', '.join(prob.split('.')[0] for prob in ready)}'\n")
			os.system(f'git commit -m "solved contest problems '
					  f'{", ".join(prob.split(".")[0] for prob in ready)}"')

			self.output_callback("Pulling latest changes...\n")
			os.system("git pull --rebase --autostash")

			self.output_callback("Pushing to GitHub...\n")
			os.system("git push origin main")

			os.chdir("..")
			self.output_callback(f"{', '.join(prob.split('.')[0] for prob in ready)} "
								 f"pushed to Github\n")
			save_queue(pending)
			if pending:
				self.output_callback(f"--- Contest Queue Updated ---\n\n")
			else:
				self.output_callback(f"--- Contest Queue Cleared ---\n\n")
		except Exception as e:
			self.output_callback(f"Failed to process queue. Error: {str(e)}\n\n")


class FileTab:
	"""Represents a single file tab with its own state"""
	def __init__(self, file_path, prob_id, lang):
		self.file_path = file_path
		self.prob_id = prob_id
		self.lang = lang
		self.file_name = os.path.basename(file_path)
		self.input_content = "Paste test input here BEFORE RUNNING THE CODE..."  # Store input for this tab


class CFMT_GUI:
	def __init__(self, root, folder, cf_handle):
		self.root = root
		self.git_thread = None
		self.solve_folder = folder
		self.cf_handle = cf_handle

		# Multi-file management
		self.file_tabs = []
		self.current_tab_index = None

		self.available_themes = [
			'litera', 'flatly', 'minty', 'sandstone', 'morph',
			'solar', 'superhero', 'darkly', 'cyborg', 'vapor'
		]

		self.init_ui()
		self.root.after(500, self.start_processing_queue)

	def init_ui(self):
		self.root.title("CFMT - Codeforces Management Tool")
		self.root.geometry("1440x720")

		try:
			self.root.iconbitmap("codeforces.ico")
		except Exception as e:
			pass

		main_frame = ttk.Frame(self.root, padding="20")
		main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(0, weight=1)
		main_frame.columnconfigure(0, weight=1)

		# Header
		header_frame = ttk.Frame(main_frame)
		header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
		header_frame.columnconfigure(0, weight=1)

		header = ttk.Label(header_frame, text="Codeforces Management Tool",
						   font=("Segoe UI", 24, "bold"))
		header.grid(row=0, column=0, sticky=tk.W)

		self.theme_btn = ttk.Menubutton(header_frame,
										text=f"{self.root.style.theme.name.capitalize()}",
										bootstyle="primary-outline")
		self.theme_btn.grid(row=0, column=1, sticky=tk.E, padx=(10, 5))

		theme_menu = tk.Menu(self.theme_btn, tearoff=0)
		self.theme_btn["menu"] = theme_menu

		for theme in self.available_themes:
			theme_menu.add_command(label=theme.capitalize(),
								   command=lambda t=theme: self.change_theme(t))

		self.tab_buttons = []

		# Problem Input
		prob_frame = ttk.Frame(main_frame)
		prob_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
		prob_frame.columnconfigure(1, weight=1)

		ttk.Label(prob_frame, text="Problem ID:",
				  font=("Segoe UI", 11, "bold")).grid(row=0, column=0, padx=(0, 10))

		self.prob_input = ttk.Entry(prob_frame, font=("Segoe UI", 10))
		self.prob_input.insert(0, "e.g., 2160B")
		self.prob_input.bind("<FocusIn>", lambda e: self.prob_input.delete(0, tk.END)
		if self.prob_input.get() == "e.g., 2160B" else None)
		self.prob_input.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

		# Language selection
		lang_frame = ttk.Frame(main_frame)
		lang_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)

		ttk.Label(lang_frame, text="Language:",
				  font=("Segoe UI", 11, "bold")).grid(row=0, column=0, padx=(0, 10))

		self.current_lang = tk.StringVar(value='py')
		ttk.Radiobutton(lang_frame, text="Python",
						variable=self.current_lang, value="py").grid(row=0, column=1, padx=5)
		ttk.Radiobutton(lang_frame, text="C++",
						variable=self.current_lang, value="cpp").grid(row=0, column=2, padx=5)

		# Create file button
		self.create_btn = ttk.Button(main_frame, text="Create Code File",
									 command=self.create_file, bootstyle="primary")
		self.create_btn.grid(row=4, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

		# Action buttons
		actions_frame = ttk.Frame(main_frame)
		actions_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=10)
		actions_frame.columnconfigure([0, 1, 2], weight=1)

		self.compile_btn = ttk.Button(actions_frame, text="Compile (C++)",
									  command=self.compile_code, state="disabled")
		self.compile_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)

		self.run_btn = ttk.Button(actions_frame, text="Run Code",
								  command=self.run_code, state="disabled")
		self.run_btn.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

		self.git_btn = ttk.Button(actions_frame, text="Git Push",
								  command=self.git_push, state="disabled")
		self.git_btn.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=5)

		# Bottom section with Logs and Inputs side by side
		bottom_frame = ttk.Frame(main_frame)
		bottom_frame.grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
		bottom_frame.columnconfigure([0, 1], weight=1)
		main_frame.rowconfigure(6, weight=1)

		# Left: Logs
		left_frame = ttk.Frame(bottom_frame)
		left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 5))
		left_frame.rowconfigure(1, weight=1)
		left_frame.columnconfigure(0, weight=1)

		ttk.Label(left_frame, text="Logs & Outputs:",
				  font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

		self.log_text = ScrolledText(left_frame, wrap=tk.WORD,
									 font=("Consolas", 10), autohide=True)
		self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
		self.log_text.text.config(state="disabled")

		# Right: Inputs
		right_frame = ttk.Frame(bottom_frame)
		right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 5))
		right_frame.rowconfigure(1, weight=1)
		right_frame.columnconfigure(0, weight=1)
		bottom_frame.rowconfigure(0, weight=1)

		ttk.Label(right_frame, text="Input Box:",
				  font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

		self.input_box = ScrolledText(right_frame, wrap=tk.WORD,
									  font=("Consolas", 10), autohide=True)
		self.input_box.insert("1.0", "Paste test input here BEFORE RUNNING THE CODE...")
		self.input_box.bind("<FocusIn>", self.clear_input_placeholder)
		self.input_box.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

		# Tab bar at the bottom spanning full width
		tab_bar_frame = ttk.Frame(main_frame)
		tab_bar_frame.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
		tab_bar_frame.columnconfigure(0, weight=1)

		ttk.Label(
			tab_bar_frame,
			text="Open Files:",
			font=("Segoe UI", 11, "bold")
		).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

		# Horizontal tab container with border
		tabs_border_frame = ttk.Labelframe(tab_bar_frame, padding=10, relief="solid", borderwidth=1)
		tabs_border_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))

		self.tabs_container = ttk.Frame(tabs_border_frame)
		self.tabs_container.pack(fill=tk.X)

	def update_tab_display(self):
		"""Refresh the tab buttons display as a horizontal bar"""

		# Destroy all previous tab widgets
		for widget in self.tabs_container.winfo_children():
			widget.destroy()

		self.tab_buttons.clear()

		for idx, tab in enumerate(self.file_tabs):
			is_active = (idx == self.current_tab_index)

			tab_frame = ttk.Frame(self.tabs_container)
			tab_frame.pack(side=tk.LEFT, padx=2)

			btn = ttk.Button(
				tab_frame,
				text=f"{tab.prob_id}.{tab.lang}",
				command=lambda i=idx: self.switch_tab(i),
				bootstyle="primary" if is_active else "secondary-outline",
				width=10
			)
			btn.pack(side=tk.LEFT)

			close_btn = ttk.Button(
				tab_frame,
				text=f"\u2715",
				command=lambda i=idx: self.close_tab(i),
				bootstyle="danger-outline",
				width=3
			)
			close_btn.pack(side=tk.LEFT, padx=(2, 0))

			self.tab_buttons.append(btn)

	def switch_tab(self, index):
		"""Switch to a different tab"""
		if 0 <= index < len(self.file_tabs):
			# Save current tab's input before switching
			if self.current_tab_index is not None and 0 <= self.current_tab_index < len(self.file_tabs):
				current_input = self.input_box.get("1.0", tk.END).strip()
				self.file_tabs[self.current_tab_index].input_content = current_input

			self.current_tab_index = index
			tab = self.file_tabs[index]

			self.prob_input.delete(0, tk.END)
			self.prob_input.insert(0, tab.prob_id)
			self.current_lang.set(tab.lang)

			# Restore the input for this tab
			self.input_box.delete("1.0", tk.END)
			self.input_box.insert("1.0", tab.input_content)

			self.update_tab_display()
			self.append_log(f"\n--- Switched to {tab.file_name} ---\n")

			self.compile_btn.config(state="normal")
			self.run_btn.config(state="normal")
			if self.is_git_logged_in():
				self.git_btn.config(state="normal")

	def close_tab(self, index):
		"""Close a specific tab"""
		if 0 <= index < len(self.file_tabs):
			tab = self.file_tabs[index]
			self.append_log(f"--- Closed {tab.file_name} ---\n")

			self.file_tabs.pop(index)

			if len(self.file_tabs) == 0:
				self.current_tab_index = None
				self.input_box.delete("1.0", tk.END)
				self.input_box.insert("1.0", "Paste test input here BEFORE RUNNING THE CODE...")
				self.compile_btn.config(state="disabled")
				self.run_btn.config(state="disabled")
				self.git_btn.config(state="disabled")
			elif self.current_tab_index == index:
				# Switch to the previous tab (or first if closing the first tab)
				new_index = max(0, index - 1)
				self.current_tab_index = new_index

				# Load the new tab's content
				new_tab = self.file_tabs[new_index]
				self.prob_input.delete(0, tk.END)
				self.prob_input.insert(0, new_tab.prob_id)
				self.current_lang.set(new_tab.lang)

				# Restore the input for the new tab
				self.input_box.delete("1.0", tk.END)
				self.input_box.insert("1.0", new_tab.input_content)

				self.compile_btn.config(state="normal")
				self.run_btn.config(state="normal")
				if self.is_git_logged_in():
					self.git_btn.config(state="normal")
			elif self.current_tab_index > index:
				self.current_tab_index -= 1

			self.update_tab_display()

	def get_current_tab(self):
		"""Get the currently active tab, or None"""
		if self.current_tab_index is not None and 0 <= self.current_tab_index < len(self.file_tabs):
			return self.file_tabs[self.current_tab_index]
		return None

	def create_file(self):
		prob_id = self.prob_input.get().strip()

		is_valid, error_msg = self.validate_problem_id(prob_id)
		if not is_valid or prob_id == "e.g., 2160B":
			messagebox.showwarning("Invalid Input", error_msg or "Enter a valid Problem ID!")
			return

		ext = self.current_lang.get()
		file_name = f"{prob_id}.{ext}"
		file_path = os.path.join(self.solve_folder, file_name)

		for idx, tab in enumerate(self.file_tabs):
			if tab.file_path == file_path:
				self.switch_tab(idx)
				self.append_log(f"--- {file_name} is already open ---\n")
				return

		if not os.path.exists(file_path):
			template = f"{ext}_template.txt"
			if os.path.exists(template):
				with open(template, "r") as t, open(file_path, "w") as cf:
					cf.write(t.read())
			else:
				open(file_path, "w").close()

		if os.name == "nt":
			subprocess.Popen(f'code "{file_path}"', shell=True,
							 creationflags=subprocess.CREATE_NO_WINDOW)
		else:
			subprocess.Popen(f'code "{file_path}"', shell=True)

		# Save current tab's input before creating new tab
		if self.current_tab_index is not None and 0 <= self.current_tab_index < len(self.file_tabs):
			current_input = self.input_box.get("1.0", tk.END).strip()
			self.file_tabs[self.current_tab_index].input_content = current_input

		new_tab = FileTab(file_path, prob_id, ext)
		self.file_tabs.append(new_tab)
		self.current_tab_index = len(self.file_tabs) - 1

		self.update_tab_display()

		self.input_box.delete("1.0", tk.END)
		self.input_box.insert("1.0", new_tab.input_content)
		self.append_log(f"--- {file_name} created and opened ---\n")

		self.compile_btn.config(state="normal")
		self.run_btn.config(state="normal")

		if not self.is_git_logged_in():
			self.append_log(f"--- To access Git push operation: \n"
							f"--- Download and Log into Github Desktop app from: "
							f"'https://desktop.github.com/download/'\n"
							f"--- Otherwise, your solutions will be stored in {self.solve_folder}, "
							f"you can push the changes later on.\n")
			self.git_btn.config(state="disabled")
		else:
			self.git_btn.config(state="normal")

	def compile_code(self):
		tab = self.get_current_tab()
		if not tab:
			messagebox.showwarning("No File Selected", "Please create or select a file first.")
			return

		if tab.lang == "py":
			self.append_log("Python does not need compilation.\n")
			return

		cmd = f'g++ -std=c++14 "{tab.file_path}" -o a.exe'
		self.append_log(f"\nCompiling {tab.file_name}...\n")
		result = os.system(cmd)
		if result == 0:
			self.append_log("\nCompiled successfully!\n")
		else:
			self.append_log("\nCompilation failed!\n")

	def run_code(self):
		tab = self.get_current_tab()
		if not tab:
			messagebox.showwarning("No File Selected", "Please create or select a file first.")
			return

		self.append_log(f"\n--- Running {tab.prob_id} ---\n")
		user_input = self.input_box.get("1.0", tk.END)

		if user_input.strip() == "Paste test input here BEFORE RUNNING THE CODE...":
			user_input = ""

		try:
			if tab.lang == "cpp":
				cmd = ["a.exe"]
			elif tab.lang == "py":
				cmd = ["python", tab.file_path]

			process = subprocess.Popen(cmd, stdin=subprocess.PIPE,
									   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
									   text=True)

			stdout, stderr = process.communicate(user_input)

			if stdout.strip():
				self.append_log("-- Output:\n")
				self.append_log(stdout + "\n")

			if stderr.strip():
				self.append_log("\n[Error]\n" + stderr + "\n")

		except Exception as e:
			self.append_log(f"\nRuntime Error: {str(e)}\n")

	def git_push(self):
		tab = self.get_current_tab()
		if not tab:
			messagebox.showwarning("No File Selected", "Please create or select a file first.")
			return

		current_index = self.current_tab_index
		self.git_btn.config(state="disabled")
		self.append_log("\n--- Git Push Started ---\n")

		def on_finished(close_tab=False):
			def update_ui():
				self.git_btn.config(state="normal")
				if close_tab and 0 <= current_index < len(self.file_tabs):
					self.close_tab(current_index)

			self.root.after(0, update_ui)

		def on_output(text):
			self.root.after(0, lambda: self.append_log(text))

		self.git_thread = GitPushThread(tab.file_path, tab.prob_id,
										self.solve_folder, self.cf_handle,
										on_output, on_finished)
		self.git_thread.start()

	def change_theme(self, theme_name):
		self.root.style.theme_use(theme_name)
		self.theme_btn.config(text=f"{theme_name.capitalize()}")
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
		if not prob_id:
			return False, "Problem ID mustn't be empty."
		if not re.match(r'^[0-9]+[A-Z][1-9]*', prob_id):
			return False, "This doesn't look like a valid problem ID."
		return True, ""

	@staticmethod
	def is_git_logged_in():
		name = subprocess.getoutput("git config --global user.name").strip()
		email = subprocess.getoutput("git config --global user.email").strip()
		return bool(name) and bool(email)

	def start_processing_queue(self):
		def on_output(text):
			self.root.after(0, lambda: self.append_log(text))

		queue_thread = GitPushQueueThread(self.solve_folder, on_output)
		queue_thread.start()


def main():
	default_theme = "darkly"
	if os.path.exists("theme_preference.txt"):
		try:
			with open("theme_preference.txt", "r") as f:
				saved_theme = f.read().strip()
				if saved_theme:
					default_theme = saved_theme
		except:
			pass

	root = ttk.Window(themename=default_theme)
	root.withdraw()

	user_config = load_user_config()
	if user_config is None or not validate_user_config(user_config):
		dialogue = UserInfoDialog(root)
		root.wait_window(dialogue)

		github_username = dialogue.username
		git_repo_name = dialogue.repo
		cf_handle = dialogue.cf_handle

		if not github_username or not git_repo_name or not cf_handle:
			messagebox.showerror("Error", "All fields are required.")
			sys.exit(1)

		user_config = {
			"github_username": github_username,
			"git_repo_name": git_repo_name,
			"cf_username": cf_handle
		}
		save_user_config(user_config)

	git_repo_name = user_config["git_repo_name"]
	cf_handle = user_config["cf_username"]

	root.deiconify()
	app = CFMT_GUI(root, git_repo_name, cf_handle)
	root.mainloop()


if __name__ == "__main__":
	main()
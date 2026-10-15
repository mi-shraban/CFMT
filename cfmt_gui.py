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
	def __init__(self, parent, current_username="", current_repo="", current_cf_handle="", is_settings=False):
		super().__init__(parent)
		self.is_settings = is_settings
		self.title("CFMT Settings" if is_settings else "CF Repo Setup")
		self.geometry("450x330")
		self.resizable(False, False)
		try:
			self.iconbitmap("codeforces.ico")
		except Exception:
			pass

		ttk.Label(self, text="GitHub Username:", font=("Segoe UI", 11)).pack(pady=(10, 2))
		self.username_entry = ttk.Entry(self, width=40)
		self.username_entry.pack()
		if current_username:
			self.username_entry.insert(0, current_username)

		ttk.Label(self, text="CF Repository Name:", font=("Segoe UI", 11)).pack(pady=(10, 2))
		self.repo_entry = ttk.Entry(self, width=40)
		self.repo_entry.pack()
		if current_repo:
			self.repo_entry.insert(0, current_repo)

		ttk.Label(self, text="CF Username / Handle:", font=("Segoe UI", 11)).pack(pady=(10, 2))
		self.cf_handle_entry = ttk.Entry(self, width=40)
		self.cf_handle_entry.pack()
		if current_cf_handle:
			self.cf_handle_entry.insert(0, current_cf_handle)

		btn_frame = ttk.Frame(self)
		btn_frame.pack(pady=15)

		ttk.Button(btn_frame, text="Save" if is_settings else "OK", command=self.submit, bootstyle="primary").pack(side=tk.LEFT, padx=5)
		if is_settings:
			ttk.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side=tk.LEFT, padx=5)

		self.username = None
		self.repo = None
		self.cf_handle = None
		self.grab_set()

	@staticmethod
	def validate_username(username):
		if not username:
			return False, "GitHub username mustn't be empty."
		if len(username) > 39:
			return False, "Provided string too long, cannot be GitHub username."
		if not re.match(r"^[a-z\d](?:[a-z\d-]{0,37}[a-z\d])?$", username, re.IGNORECASE):
			return False, "This doesn't look like a valid GitHub username."
		return True, ""

	@staticmethod
	def validate_repo_name(reponame):
		if not reponame:
			return False, "Repository name mustn't be empty."
		if reponame.endswith(".git"):
			reponame = reponame[:-4]
		if len(reponame) > 100:
			return False, "Provided string too long, cannot be Repository name."
		if not re.match(r"^[A-Za-z0-9._-]{1,100}$", reponame):
			return False, "This doesn't look like a valid Repository name."
		return True, reponame

	@staticmethod
	def validate_cf_handle(cf_handle):
		if not cf_handle:
			return False, "Codeforces handle mustn't be empty."
		try:
			data = requests.get(
				f"https://codeforces.com/api/user.info?handles={cf_handle}&checkHistoricHandles=False",
				timeout=10
			).json()
			if data.get("status") == 'OK':
				return True, ""
			else:
				return False, "Codeforces username wasn't found. Recheck spelling."
		except Exception as e:
			return False, f"Could not connect to Codeforces API: {e}"

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
			if not self.is_settings:
				use_existing = messagebox.askyesno(
					"Repository Already Cloned",
					f"{reponame} already exists locally.\n"
					f"Yes: Use existing repository folder.\n"
					f"No: Choose a different repository name.\n"
				)
				if not use_existing:
					return
			self.username = username
			self.repo = reponame
			self.cf_handle = cf_handle
			self.destroy()
			return

		clone_cmd = ["git", "clone", f"https://github.com/{username}/{reponame}.git"]
		clone_res = subprocess.run(clone_cmd, capture_output=True, text=True)
		if clone_res.returncode != 0:
			retry = messagebox.askretrycancel(
				"Repository Clone Failed",
				f"Failed to clone github.com/{username}/{reponame}\n"
				f"-- Check if the Repository exists on GitHub.\n"
				f"-- Recheck the spelling of username and repo.\n"
				f"-- Check your internet connection.\n\n"
				f"Details:\n{clone_res.stderr.strip()}"
			)
			if retry:
				return
			elif not self.is_settings:
				sys.exit(1)
			else:
				return

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
				f"https://codeforces.com/api/user.status?handle={self.cf_handle}&from=1&count=15",
				timeout=10
			).json()
			contest_list = requests.get(
				"https://codeforces.com/api/contest.list?gym=false",
				timeout=10
			).json()

			queue = load_queue()
			file_name = os.path.basename(self.file_path)

			if submission_list.get("status") != "OK" or contest_list.get("status") != "OK":
				return False

			for s in submission_list.get('result', []):
				contestId = f"{s.get('problem', {}).get('contestId', '')}"
				problemId = f"{contestId}{s.get('problem', {}).get('index', '')}"
				if problemId == self.prob_id and (s.get('verdict') in ('OK', 'PARTIAL')) and s.get('author', {}).get('participantType') == "CONTESTANT":
					for c in contest_list.get('result', []):
						if f"{c.get('id')}" == contestId:
							contest_end = c.get('startTimeSeconds', 0) + c.get('durationSeconds', 0)
							if file_name not in queue:
								queue[file_name] = contest_end
								save_queue(queue)
							return True
			return False
		except Exception as e:
			self.output_callback(f"Error checking contest status: {e}\n")
			return False

	def run(self):
		try:
			if self.contest_time_solve():
				self.output_callback(
					f"Added {os.path.basename(self.file_path)} to Contest Queue (Active Contest Solution).\n"
					f"Queued solutions will automatically be pushed to GitHub after the contest concludes.\n"
				)
				self.finished_callback(close_tab=True)
				return

			base_file = os.path.basename(self.file_path)

			self.output_callback(f"Adding {base_file} to Git...\n")
			add_res = subprocess.run(["git", "add", base_file], cwd=self.solve_folder, capture_output=True, text=True)
			if add_res.returncode != 0:
				self.output_callback(f"Git add warning: {add_res.stderr}\n")

			self.output_callback(f"Committing 'solved {self.prob_id}'...\n")
			commit_res = subprocess.run(["git", "commit", "-m", f"solved {self.prob_id}"], cwd=self.solve_folder, capture_output=True, text=True)
			if commit_res.returncode != 0 and "nothing to commit" not in commit_res.stdout:
				self.output_callback(f"Commit note: {commit_res.stdout or commit_res.stderr}\n")

			self.output_callback("Pulling latest changes with rebase...\n")
			pull_res = subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=self.solve_folder, capture_output=True, text=True)
			if pull_res.returncode != 0:
				self.output_callback(f"Pull warning: {pull_res.stderr or pull_res.stdout}\n")

			self.output_callback("Pushing to GitHub origin main...\n")
			push_res = subprocess.run(["git", "push", "origin", "main"], cwd=self.solve_folder, capture_output=True, text=True)
			if push_res.returncode != 0:
				self.output_callback(f"Git push notice: {push_res.stderr or push_res.stdout}\n")

			self.output_callback("Push completed successfully.\n\n")
			self.finished_callback(close_tab=True)
		except Exception as e:
			self.output_callback(f"Error during Git push: {str(e)}\n\n")
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

			self.output_callback(f"--- Processing Contest Queue ({len(ready)} ready) ---\n")
			prob_names = [p.split('.')[0] for p in ready]
			self.output_callback(f"Adding {', '.join(prob_names)} from queue to Git\n")

			subprocess.run(["git", "add"] + ready, cwd=self.solve_folder, capture_output=True, text=True)

			commit_msg = f"solved contest problems {', '.join(prob_names)}"
			self.output_callback(f"Committing '{commit_msg}'\n")
			subprocess.run(["git", "commit", "-m", commit_msg], cwd=self.solve_folder, capture_output=True, text=True)

			self.output_callback("Pulling latest changes...\n")
			subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=self.solve_folder, capture_output=True, text=True)

			self.output_callback("Pushing to GitHub...\n")
			subprocess.run(["git", "push", "origin", "main"], cwd=self.solve_folder, capture_output=True, text=True)

			self.output_callback(f"{', '.join(prob_names)} pushed to GitHub.\n")
			save_queue(pending)
			if pending:
				self.output_callback(f"--- Contest Queue: {len(pending)} solution(s) still waiting for contest end ---\n\n")
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
		self.input_content = "Paste test input here BEFORE RUNNING THE CODE..."


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
		self.root.geometry("1440x750")

		try:
			self.root.iconbitmap("codeforces.ico")
		except Exception:
			pass

		# Keyboard Shortcuts
		self.root.bind("<Control-Return>", lambda e: self.run_code())
		self.root.bind("<F5>", lambda e: self.run_code())
		self.root.bind("<F7>", lambda e: self.compile_code())

		main_frame = ttk.Frame(self.root, padding="20")
		main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(0, weight=1)
		main_frame.columnconfigure(0, weight=1)

		# Header
		header_frame = ttk.Frame(main_frame)
		header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
		header_frame.columnconfigure(0, weight=1)

		header = ttk.Label(header_frame, text="Codeforces Management Tool",
						   font=("Segoe UI", 22, "bold"))
		header.grid(row=0, column=0, sticky=tk.W)

		btn_header_group = ttk.Frame(header_frame)
		btn_header_group.grid(row=0, column=1, sticky=tk.E)

		self.settings_btn = ttk.Button(btn_header_group, text="⚙ Settings",
									   command=self.open_settings,
									   bootstyle="secondary-outline")
		self.settings_btn.pack(side=tk.LEFT, padx=5)

		self.theme_btn = ttk.Menubutton(btn_header_group,
										text=f"Theme: {self.root.style.theme.name.capitalize()}",
										bootstyle="primary-outline")
		self.theme_btn.pack(side=tk.LEFT, padx=5)

		theme_menu = tk.Menu(self.theme_btn, tearoff=0)
		self.theme_btn["menu"] = theme_menu

		for theme in self.available_themes:
			theme_menu.add_command(label=theme.capitalize(),
								   command=lambda t=theme: self.change_theme(t))

		self.tab_buttons = []

		# Problem Input
		prob_frame = ttk.Frame(main_frame)
		prob_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=8)
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
		lang_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=8)

		ttk.Label(lang_frame, text="Language:",
				  font=("Segoe UI", 11, "bold")).grid(row=0, column=0, padx=(0, 10))

		self.current_lang = tk.StringVar(value='cpp')
		ttk.Radiobutton(lang_frame, text="C++ (g++ C++17 -O2)",
						variable=self.current_lang, value="cpp").grid(row=0, column=1, padx=8)
		ttk.Radiobutton(lang_frame, text="Python",
						variable=self.current_lang, value="py").grid(row=0, column=2, padx=8)

		# Create file button
		self.create_btn = ttk.Button(main_frame, text="Create Code File",
									 command=self.create_file, bootstyle="primary")
		self.create_btn.grid(row=4, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

		# Action buttons
		actions_frame = ttk.Frame(main_frame)
		actions_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=10)
		actions_frame.columnconfigure([0, 1, 2], weight=1)

		self.compile_btn = ttk.Button(actions_frame, text="Compile (C++) [F7]",
									  command=self.compile_code, state="disabled")
		self.compile_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)

		self.run_btn = ttk.Button(actions_frame, text="Run Code [F5]",
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

		ttk.Label(right_frame, text="Input Box (Paste test case input here):",
				  font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

		self.input_box = ScrolledText(right_frame, wrap=tk.WORD,
									  font=("Consolas", 10), autohide=True)
		self.input_box.insert("1.0", "Paste test input here BEFORE RUNNING THE CODE...")
		self.input_box.bind("<FocusIn>", self.clear_input_placeholder)
		self.input_box.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

		# Tab bar at the bottom
		tab_bar_frame = ttk.Frame(main_frame)
		tab_bar_frame.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
		tab_bar_frame.columnconfigure(0, weight=1)

		ttk.Label(
			tab_bar_frame,
			text="Open Files:",
			font=("Segoe UI", 11, "bold")
		).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

		tabs_border_frame = ttk.Labelframe(tab_bar_frame, padding=8, relief="solid", borderwidth=1)
		tabs_border_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))

		self.tabs_container = ttk.Frame(tabs_border_frame)
		self.tabs_container.pack(fill=tk.X)

	def open_settings(self):
		cfg = load_user_config() or {}
		dialog = UserInfoDialog(
			self.root,
			current_username=cfg.get("github_username", ""),
			current_repo=cfg.get("git_repo_name", self.solve_folder),
			current_cf_handle=cfg.get("cf_username", self.cf_handle),
			is_settings=True
		)
		self.root.wait_window(dialog)

		if dialog.username and dialog.repo and dialog.cf_handle:
			new_cfg = {
				"github_username": dialog.username,
				"git_repo_name": dialog.repo,
				"cf_username": dialog.cf_handle
			}
			save_user_config(new_cfg)
			self.solve_folder = dialog.repo
			self.cf_handle = dialog.cf_handle
			os.makedirs(self.solve_folder, exist_ok=True)
			self.append_log(f"--- Settings Updated ---\n"
							f"GitHub: {dialog.username} | Repo: {dialog.repo} | CF: {dialog.cf_handle}\n\n")

	def update_tab_display(self):
		for widget in self.tabs_container.winfo_children():
			widget.destroy()

		self.tab_buttons.clear()

		for idx, tab in enumerate(self.file_tabs):
			is_active = (idx == self.current_tab_index)

			tab_frame = ttk.Frame(self.tabs_container)
			tab_frame.pack(side=tk.LEFT, padx=3)

			btn = ttk.Button(
				tab_frame,
				text=f"{tab.prob_id}.{tab.lang}",
				command=lambda i=idx: self.switch_tab(i),
				bootstyle="primary" if is_active else "secondary-outline",
				width=11
			)
			btn.pack(side=tk.LEFT)

			close_btn = ttk.Button(
				tab_frame,
				text="\u2715",
				command=lambda i=idx: self.close_tab(i),
				bootstyle="danger-outline",
				width=3
			)
			close_btn.pack(side=tk.LEFT, padx=(2, 0))

			self.tab_buttons.append(btn)

	def switch_tab(self, index):
		if 0 <= index < len(self.file_tabs):
			if self.current_tab_index is not None and 0 <= self.current_tab_index < len(self.file_tabs):
				current_input = self.input_box.get("1.0", tk.END).strip()
				self.file_tabs[self.current_tab_index].input_content = current_input

			self.current_tab_index = index
			tab = self.file_tabs[index]

			self.prob_input.delete(0, tk.END)
			self.prob_input.insert(0, tab.prob_id)
			self.current_lang.set(tab.lang)

			self.input_box.delete("1.0", tk.END)
			self.input_box.insert("1.0", tab.input_content)

			self.update_tab_display()
			self.append_log(f"\n--- Switched to {tab.file_name} ---\n")

			self.compile_btn.config(state="normal")
			self.run_btn.config(state="normal")
			if self.is_git_logged_in():
				self.git_btn.config(state="normal")

	def close_tab(self, index):
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
				new_index = max(0, index - 1)
				self.current_tab_index = new_index

				new_tab = self.file_tabs[new_index]
				self.prob_input.delete(0, tk.END)
				self.prob_input.insert(0, new_tab.prob_id)
				self.current_lang.set(new_tab.lang)

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
		if self.current_tab_index is not None and 0 <= self.current_tab_index < len(self.file_tabs):
			return self.file_tabs[self.current_tab_index]
		return None

	def create_file(self):
		prob_id = self.prob_input.get().strip()

		is_valid, error_msg = self.validate_problem_id(prob_id)
		if not is_valid or prob_id == "e.g., 2160B":
			messagebox.showwarning("Invalid Input", error_msg or "Enter a valid Problem ID (e.g., 2160B)!")
			return

		ext = self.current_lang.get()
		file_name = f"{prob_id}.{ext}"
		os.makedirs(self.solve_folder, exist_ok=True)
		file_path = os.path.join(self.solve_folder, file_name)

		for idx, tab in enumerate(self.file_tabs):
			if tab.file_path == file_path:
				self.switch_tab(idx)
				self.append_log(f"--- {file_name} is already open ---\n")
				return

		if not os.path.exists(file_path):
			template = f"{ext}_template.txt"
			if os.path.exists(template):
				with open(template, "r", encoding="utf-8") as t, open(file_path, "w", encoding="utf-8") as cf:
					cf.write(t.read())
			else:
				open(file_path, "w", encoding="utf-8").close()

		try:
			if os.name == "nt":
				subprocess.Popen(f'code "{file_path}"', shell=True,
								 creationflags=subprocess.CREATE_NO_WINDOW)
			else:
				subprocess.Popen(f'code "{file_path}"', shell=True)
		except Exception:
			pass

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
			self.append_log(f"--- To access Git push operations:\n"
							f"--- Configure git global user.name and user.email, or use GitHub Desktop.\n"
							f"--- Solutions are safely saved in '{self.solve_folder}/'.\n")
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

		exe_name = "a.exe" if os.name == "nt" else "a.out"
		cmd = ["g++", "-std=c++17", "-O2", tab.file_path, "-o", exe_name]
		self.append_log(f"\nCompiling {tab.file_name} (g++ -std=c++17 -O2)...\n")

		try:
			proc = subprocess.run(cmd, capture_output=True, text=True)
			if proc.returncode == 0:
				self.append_log("Compiled successfully!\n")
				if proc.stderr.strip():
					self.append_log(f"[Compiler Warnings]:\n{proc.stderr.strip()}\n")
			else:
				self.append_log("[Compilation Error]:\n")
				self.append_log(proc.stderr.strip() + "\n")
		except FileNotFoundError:
			self.append_log("[Error] 'g++' compiler not found! Make sure MinGW/GCC is installed and added to PATH.\n")
		except Exception as e:
			self.append_log(f"[Compilation Error]: {str(e)}\n")

	def run_code(self):
		tab = self.get_current_tab()
		if not tab:
			messagebox.showwarning("No File Selected", "Please create or select a file first.")
			return

		self.append_log(f"\n--- Running {tab.prob_id} ---\n")
		user_input = self.input_box.get("1.0", tk.END)

		if user_input.strip() == "Paste test input here BEFORE RUNNING THE CODE...":
			user_input = ""

		exe_name = "a.exe" if os.name == "nt" else "./a.out"
		if tab.lang == "cpp":
			check_file = "a.exe" if os.name == "nt" else "a.out"
			if not os.path.exists(check_file):
				self.append_log("[Notice] Executable not found. Compiling first...\n")
				self.compile_code()
				if not os.path.exists(check_file):
					return
			cmd = [exe_name]
		elif tab.lang == "py":
			cmd = [sys.executable, tab.file_path]

		try:
			start_time = time.time()
			process = subprocess.Popen(
				cmd,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				text=True
			)

			try:
				stdout, stderr = process.communicate(user_input, timeout=5.0)
				elapsed = time.time() - start_time

				if stdout.strip():
					self.append_log(f"-- Output ({elapsed:.2f}s):\n" + stdout + "\n")
				else:
					self.append_log(f"-- Program exited with no stdout ({elapsed:.2f}s).\n")

				if stderr.strip():
					self.append_log(f"[Stderr / Warnings]:\n" + stderr + "\n")

			except subprocess.TimeoutExpired:
				process.kill()
				process.communicate()
				self.append_log("\n[Time Limit Exceeded] Execution timed out after 5.0 seconds and was terminated.\n")

		except FileNotFoundError:
			self.append_log(f"[Execution Error] Binary or script '{cmd[0]}' not found.\n")
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
		self.theme_btn.config(text=f"Theme: {theme_name.capitalize()}")
		try:
			with open("theme_preference.txt", "w", encoding="utf-8") as f:
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
		if not re.match(r'^[0-9]+[A-Za-z][0-9]*$', prob_id):
			return False, "This doesn't look like a valid problem ID (e.g. 2160B, 1915C)."
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
			with open("theme_preference.txt", "r", encoding="utf-8") as f:
				saved_theme = f.read().strip()
				if saved_theme:
					default_theme = saved_theme
		except Exception:
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
	os.makedirs(git_repo_name, exist_ok=True)

	root.deiconify()
	app = CFMT_GUI(root, git_repo_name, cf_handle)
	root.mainloop()


if __name__ == "__main__":
	main()
import sys
import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
import ttkbootstrap as ttk
from ttkbootstrap.widgets.scrolled import ScrolledText


class GitPushThread(threading.Thread):
	def __init__(self, file_path, prob_id, solve_folder, output_callback, finished_callback):
		super().__init__(daemon=True)
		self.file_path = file_path
		self.prob_id = prob_id
		self.solve_folder = solve_folder
		self.output_callback = output_callback
		self.finished_callback = finished_callback

	def run(self):
		try:
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
			self.output_callback("Completed.\n")
		except Exception as e:
			self.output_callback(f"Error: {str(e)}\n")
		finally:
			self.finished_callback()


class CFMT_GUI:
	def __init__(self, root):
		self.root = root
		self.current_file_path = None
		self.current_lang = tk.StringVar(value='py')
		self.git_thread = None

		self.solve_folder = None
		self.available_themes = [
			'litera', 'flatly', 'minty', 'sandstone', 'morph',
			'solar', 'superhero', 'darkly', 'cyborg', 'vapor'
		]
		# 5 light themes, 5 dark themes
		self.init_user_info()
		self.init_ui()

	def init_user_info(self):
		if not os.path.exists("user_info.txt"):
			self.setup_user_info()

		with open("user_info.txt", "r") as f:
			self.solve_folder = f.read().strip()

		# Clone repo if missing
		if not os.path.exists(self.solve_folder):
			messagebox.showinfo("Cloning Repo",
								f"Cloning repository: {self.solve_folder}")
			os.system(f"git clone https://github.com/{self.github_username}/{self.solve_folder}.git")

	def setup_user_info(self):
		github_username = simpledialog.askstring("Setup Required",
												 "GitHub username:")
		if not github_username or not github_username.strip():
			messagebox.showerror("Error", "This field is required.")
			sys.exit(1)

		git_repo_name = simpledialog.askstring("Setup Required",
											   "Your CF Repository name:")
		if not git_repo_name or not git_repo_name.strip():
			messagebox.showerror("Error", "This field is required.")
			sys.exit(1)

		self.github_username = github_username.strip()

		with open("user_info.txt", "w") as f:
			f.write(git_repo_name.strip())

		os.system(f"git clone https://github.com/{github_username.strip()}/{git_repo_name.strip()}.git")

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

	def create_file(self):
		prob_id = self.prob_input.get().strip()
		if not prob_id or prob_id == "e.g., 2160B":
			messagebox.showwarning("Error", "Enter a Problem ID first!")
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
		os.system(f'code "{file_path}"')

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

	def is_git_logged_in(self):
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
			on_output,
			on_finished
		)
		self.git_thread.start()


def main():
	# Load saved theme preference or use default
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
	app = CFMT_GUI(root)
	root.mainloop()


if __name__ == "__main__":
	main()
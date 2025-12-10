import sys
import os
import subprocess
from PySide6.QtWidgets import (
	QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
	QLineEdit, QPushButton, QTextEdit, QRadioButton, QButtonGroup, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon


class GitPushThread(QThread):
	output_signal = Signal(str)
	finished_signal = Signal()

	def __init__(self, file_path, prob_id, solve_folder):
		super().__init__()
		self.file_path = file_path
		self.prob_id = prob_id
		self.solve_folder = solve_folder

	def run(self):
		try:
			os.chdir(self.solve_folder)

			self.output_signal.emit(f"Adding {os.path.basename(self.file_path)}...")
			os.system(f"git add {os.path.basename(self.file_path)}")

			self.output_signal.emit(f"Committing solved {self.prob_id}...")
			os.system(f'git commit -m "solved {self.prob_id}"')

			self.output_signal.emit("Pulling latest changes...")
			os.system("git pull --rebase --autostash")

			self.output_signal.emit("Pushing to GitHub...")
			os.system("git push origin main")

			os.chdir("..")
			self.output_signal.emit("\nSuccess! Git push complete.")
		except Exception as e:
			self.output_signal.emit(f"Error: {str(e)}")
		finally:
			self.finished_signal.emit()


class CFMT_GUI(QMainWindow):
	def __init__(self):
		super().__init__()
		self.current_file_path = None
		self.current_lang = 'py'
		self.git_thread = None

		self.solve_folder = None
		self.init_user_info()

		self.init_ui()

	def init_user_info(self):
		if not os.path.exists("user_info.txt"):
			self.setup_user_info()

		with open("user_info.txt", "r") as f:
			self.solve_folder = f.read().strip()

		# Clone repo if missing
		if not os.path.exists(self.solve_folder):
			QMessageBox.information(self, "Cloning Repo",
									f"Cloning repository: {self.solve_folder}")
			os.system(f"git clone https://github.com/{self.github_username}/{self.solve_folder}.git")

	def setup_user_info(self):
		github_username = self.popup_input("GitHub username:")
		git_repo_name = self.popup_input("Your CF Repository name:")

		self.github_username = github_username

		with open("user_info.txt", "w") as f:
			f.write(git_repo_name)

		os.system(f"git clone https://github.com/{github_username}/{git_repo_name}.git")

	def popup_input(self, message):
		text, ok = QInputDialog.getText(self, "Setup Required", message)
		if not ok or not text.strip():
			QMessageBox.critical(self, "Error", "This field is required.")
			sys.exit(1)
		return text.strip()

	def init_ui(self):
		self.setWindowTitle("CFMT GUI")
		self.setWindowIcon(QIcon("codeforces.ico"))
		self.setMinimumSize(1280, 640)

		self.set_dark_theme()

		central = QWidget()
		self.setCentralWidget(central)
		layout = QVBoxLayout(central)

		# Header
		header = QLabel("CFMT GUI")
		header.setFont(QFont("Arial", 24, QFont.Bold))
		header.setAlignment(Qt.AlignCenter)
		layout.addWidget(header)

		# Problem Input
		prob_layout = QHBoxLayout()
		prob_layout.addWidget(QLabel("Problem ID:"))
		self.prob_input = QLineEdit()
		self.prob_input.setPlaceholderText("e.g., 2160B")
		prob_layout.addWidget(self.prob_input)
		layout.addLayout(prob_layout)

		# Language selection
		lang_layout = QHBoxLayout()
		lang_label = QLabel("Language:")
		lang_layout.addWidget(lang_label)

		self.lang_group = QButtonGroup()
		self.cpp_radio = QRadioButton("C++")
		self.py_radio = QRadioButton("Python")
		self.lang_group.addButton(self.cpp_radio)
		self.lang_group.addButton(self.py_radio)
		self.py_radio.setChecked(True)

		self.cpp_radio.toggled.connect(lambda: self.set_language("cpp"))
		self.py_radio.toggled.connect(lambda: self.set_language("py"))

		lang_layout.addWidget(self.cpp_radio)
		lang_layout.addWidget(self.py_radio)
		layout.addLayout(lang_layout)

		# Create file button
		self.create_btn = QPushButton("Create Code File")
		self.create_btn.setMinimumHeight(40)
		self.create_btn.clicked.connect(self.create_file)
		layout.addWidget(self.create_btn)

		# Action buttons
		actions = QHBoxLayout()
		self.compile_btn = QPushButton("Compile (C++)")
		self.compile_btn.clicked.connect(self.compile_code)
		self.compile_btn.setEnabled(False)

		self.run_btn = QPushButton("Run Code")
		self.run_btn.clicked.connect(self.run_code)
		self.run_btn.setEnabled(False)

		self.git_btn = QPushButton("Git Push")
		self.git_btn.clicked.connect(self.git_push)
		self.git_btn.setEnabled(False)

		actions.addWidget(self.compile_btn)
		actions.addWidget(self.run_btn)
		actions.addWidget(self.git_btn)
		layout.addLayout(actions)

		bottom_layout = QHBoxLayout()

		# Left: Logs
		left_box_layout = QVBoxLayout()
		left_box_layout.addWidget(QLabel("Logs & Outputs:"))
		self.output_text = QTextEdit()
		self.output_text.setReadOnly(True)
		left_box_layout.addWidget(self.output_text)

		# Right: Running Code
		right_box_layout = QVBoxLayout()
		right_box_layout.addWidget(QLabel("Input Box:"))
		self.unsolved_box = QTextEdit()
		self.unsolved_box.setPlaceholderText("Paste test input here BEFORE RUNNING THE CODE...")
		right_box_layout.addWidget(self.unsolved_box)

		# Add both boxes to bottom area
		bottom_layout.addLayout(left_box_layout, 1)  # stretch = 1
		bottom_layout.addLayout(right_box_layout, 1)  # equal size

		layout.addLayout(bottom_layout)

	def set_language(self, lang):
		self.current_lang = lang

	def create_file(self):
		prob_id = self.prob_input.text().strip()
		if not prob_id:
			QMessageBox.warning(self, "Error", "Enter a Problem ID first!")
			return

		ext = "py" if self.current_lang == "py" else "cpp"
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

		self.unsolved_box.clear()
		self.unsolved_box.setPlaceholderText("Paste test input here BEFORE RUNNING THE CODE...")
		self.output_text.append(f"--- {file_name} created ---\n")
		self.compile_btn.setEnabled(True)
		self.run_btn.setEnabled(True)
		self.git_btn.setEnabled(True)
		if self.is_git_logged_in():
			self.output_text.append(f"--- To access Git push operation: \n"
									f"--- Download and Log into Github Desktop app from: "
									f"'https://desktop.github.com/download/'\n"
									f"--- Otherwise, your solutions will be stored in {self.solve_folder}, "
									f"you can push the changes later on.")
			self.git_btn.setEnabled(False)

	def compile_code(self):
		if self.current_lang == "py":
			self.output_text.append("Python does not need compilation.\n")
			return

		cmd = f'g++ -std=c++14 "{self.current_file_path}" -o a.exe'
		self.output_text.append(f"\nCompiling...\n")
		result = os.system(cmd)
		if result == 0:
			self.output_text.append("\nCompiled successfully!\n")
		else:
			self.output_text.append("\nCompilation failed!\n")

	def run_code(self):
		prob_id = self.prob_input.text().strip()
		if not prob_id:
			QMessageBox.warning(self, "\nError", "Enter a Problem ID first!")
			return
		self.output_text.append(f"\n--- Running {prob_id} ---\n")
		user_input = self.unsolved_box.toPlainText()

		try:
			if self.current_lang == "cpp":
				cmd = ["a.exe"]

			elif self.current_lang == "py":
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
				self.output_text.append("-- Output:\n")
				self.output_text.append(stdout)

			if stderr.strip():
				self.output_text.append("\n[Error]\n" + stderr)

		except Exception as e:
			self.output_text.append(f"\nRuntime Error: {str(e)}")

	def is_git_logged_in(self):
		name = subprocess.getoutput("git config --global user.name").strip()
		email = subprocess.getoutput("git config --global user.email").strip()
		return bool(name) and bool(email)

	def git_push(self):
		prob_id = self.prob_input.text().strip()

		self.git_btn.setEnabled(False)
		self.output_text.append("\n--- Git Push Started ---\n")

		self.git_thread = GitPushThread(
			self.current_file_path,
			prob_id,
			self.solve_folder
		)
		self.git_thread.output_signal.connect(self.output_text.append)
		self.git_thread.finished_signal.connect(lambda: self.git_btn.setEnabled(True))
		self.git_thread.start()

	def set_dark_theme(self):
		self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #121212;
                color: #d8e2dc;
            }
            QLabel {
                color: #d8e2dc;
            }
            QLineEdit {
                background-color: #1e1e1e;
                border: 2px solid #2a2a2a;
                border-radius: 5px;
                padding: 8px;
                color: #d8e2dc;
            }
            QLineEdit:focus {
                border: 2px solid #00bcd4;
            }
            QPushButton {
                background-color: #00bcd4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0097a7;
            }
            QPushButton:pressed {
                background-color: #264B5D;
            }
            QPushButton:disabled {
                background-color: #3e3e4e;
                color: #666;
            }
            QTextEdit {
                background-color: #2a2a2a;
                border: 2px solid #3e3e4e;
                border-radius: 5px;
                color: #00ff00;
                padding: 10px;
            }
            QRadioButton {
                color: #d8e2dc;
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)


def main():
	app = QApplication(sys.argv)
	app.setStyleSheet("""
        QWidget {
            background-color: #1e1e1e;
            color: cyan;
            font-weight: bold;
        }
        QLineEdit, QTextEdit {
            background-color: #1a1a1a;
            color: cyan;
            border: 1px solid cyan;
            padding: 4px;
        }
        QPushButton {
            background-color: #111;
            color: cyan;
            border: 1px solid cyan;
            padding: 6px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #222;
        }
        QInputDialog {
            background-color: #1e1e1e;
            color: cyan;
            font-weight: bold;
        }
        QLabel {
            color: cyan;
            font-weight: bold;
        }
    """)
	cfmt = CFMT_GUI()
	cfmt.show()
	sys.exit(app.exec())


if __name__ == "__main__":
	main()
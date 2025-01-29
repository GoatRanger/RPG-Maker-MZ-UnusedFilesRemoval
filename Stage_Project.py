import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from threading import Thread

"""
Filename: Stage_Project.py
Purpose: Copies an RPG Maker MZ (or really any folder structure) into a "staging" directory.
Author: Karl Gossett
Created: 2024-11-22
License: MIT
    Copyright (c) 2024 Karl Gossett

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

Notes:
- This script copies the entire structure into a new folder, which is normally used for processing just before deployment.
- The directory used is the same as the project's main directory. 
- *** USE WITH CAUTION *** It will erase any existing directory in the staging folder with that name if it already exists. 
- It is designed to work with the accompanying Unused_assets.py, which removes unused assets from your project.
- Don't forget to open the staging directory project as the current project before deployment :)
"""

def copy_game_to_staging(repo_path, staging_path, skip_dirs, progress_callback):
    """Copies the game from the repository to the staging folder."""
    try:
        
        if os.path.exists(staging_path):
            shutil.rmtree(staging_path)

        def copy_with_progress(src, dst):
            
            try:
                with open(src, "rb") as fsrc:
                    with open(dst, "wb") as fdst:
                        while True:
                            buf = fsrc.read(4096)
                            if not buf:
                                break
                            fdst.write(buf)
                progress_callback()  # Call progress_callback after copying each file
            except Exception:
                print(f"Error: {Exception}")

        for root, _, files in os.walk(repo_path):
            relative_path = os.path.relpath(root, repo_path)
            if any(dir_to_skip in relative_path.split(os.sep) for dir_to_skip in skip_dirs):
                continue
            os.makedirs(os.path.join(staging_path, relative_path), exist_ok=True)
            for file in files:
                src_path = os.path.join(root, file)
                dst_path = os.path.join(staging_path, relative_path, file)
                copy_with_progress(src_path, dst_path)  # Call copy_with_progress with src and dst paths

        print(f"Game copied to staging: {staging_path}")
    except Exception as e:
        print(f"Error copying game to staging: {e}")

def browse_directory():
    """Opens a directory selection dialog."""
    directory = filedialog.askdirectory()
    if directory:
        # Validate the directory
        credits_path = os.path.join(directory, "credits.html")
        if os.path.exists(credits_path):
            directory_entry.delete(0, tk.END)
            directory_entry.insert(0, directory)
        else:
            messagebox.showerror("Error", "Invalid RPG Maker MZ project directory: 'credits.html' not found.")

def browse_staging_directory():
    """Opens a directory selection dialog for the staging directory."""
    directory = filedialog.askdirectory()
    if directory:
        staging_entry.delete(0, tk.END)
        staging_entry.insert(0, directory)

def start_process():
    """Starts the copy and analysis process."""
    repo_path = directory_entry.get()
    staging_base = staging_entry.get()
    if not repo_path:
        messagebox.showerror("Error", "Please select a directory.")
        return
    staging_dir = os.path.basename(repo_path)
    staging_path = f"{staging_base}/{staging_dir}"

    start_button.config(state=tk.DISABLED)
    progress_bar.config(mode="determinate", value=0)
    progress_label.config(text="Copying files...")

    thread = Thread(target=copy_and_analyze, args=(repo_path, staging_path))
    thread.start()

def copy_and_analyze(repo_path, staging_path):
    """Performs the copy and analysis with progress updates."""
    print (f'Source: {repo_path} -> {staging_path}')
    skip_dirs = ['.git','.vs','DatabaseCleanUpTool','save']
    file_count = 0
    total_bytes = 0
    copied_files = 0
    for root, _, files in os.walk(repo_path):
        relative_path = os.path.relpath(root, repo_path)
        if any(dir_to_skip in relative_path.split(os.sep) for dir_to_skip in skip_dirs):
            continue
        file_count += len(files)

    def update_progress():
        """Updates the progress bar."""
        nonlocal copied_files
        nonlocal file_count
        copied_files += 1
        progress = (copied_files / file_count) * 100
        progress_bar.config(value=progress)
        progress_label.config(text=f"Copying files... {copied_files}/{file_count}")
        app.update_idletasks()

    def get_current_directory():
        """Gets the current directory of the running script."""
        if getattr(sys, 'frozen', False):
            # If the script is packaged into an executable, use this
            return os.path.dirname(sys.executable)
        else:
            # If the script is running as a .py file, use this
            return os.path.dirname(os.path.abspath(__file__))



        # Construct the full path to Unused_assets_Gem.py

    copy_game_to_staging(repo_path, staging_path, skip_dirs, update_progress)

    app.after(0, lambda: progress_label.config(text="Analyzing files..."))
    app.after(0, lambda: progress_label.config(text="Done."))
    print(f'Passing {staging_path} to unused assets finder')
    # Get the current directory of this program
    current_directory = get_current_directory()
    unused_assets_path = os.path.join(current_directory, "Unused_assets.py")
    app.after(0, lambda: subprocess.Popen(["python", unused_assets_path, staging_path]))
    app.after(0, lambda: messagebox.showinfo("Success", "Game copied to staging directory and unused assets removed."))
    app.after(0, lambda: app.destroy())  # Close the GUI
    
app = tk.Tk()
app.title("Game Deployment Pipeline")

frame = tk.Frame(app)
frame.pack(padx=10, pady=10)

directory_label = tk.Label(frame, text="Game Repository:")
directory_label.pack(side=tk.LEFT)

directory_entry = tk.Entry(frame, width=50)
directory_entry.pack(side=tk.LEFT, padx=5)

browse_button = tk.Button(frame, text="Browse", command=browse_directory)
browse_button.pack(side=tk.LEFT)

# Frame for staging directory selection
frame_staging = tk.Frame(app)
frame_staging.pack(padx=10, pady=5)  # Added some padding

staging_label = tk.Label(frame_staging, text="Staging Directory:")
staging_label.pack(side=tk.LEFT)

staging_entry = tk.Entry(frame_staging, width=50)
staging_entry.pack(side=tk.LEFT, padx=5)

browse_staging_button = tk.Button(frame_staging, text="Browse", command=browse_staging_directory)
browse_staging_button.pack(side=tk.LEFT)

progress_bar = ttk.Progressbar(app, orient="horizontal", length=400, mode="indeterminate")
progress_bar.pack(pady=10)

progress_label = tk.Label(app, text="")
progress_label.pack()

start_button = tk.Button(app, text="Start", command=start_process)
start_button.pack(pady=10)

app.mainloop()
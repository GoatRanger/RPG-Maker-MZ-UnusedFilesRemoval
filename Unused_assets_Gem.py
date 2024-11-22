import os
import tkinter as tk
import json
import sys
import re
from tkinter import ttk, filedialog, messagebox
from threading import Thread

"""
Filename: Unused_assets_Gem.py
Purpose: Identifies and optionally removes unused files in an RPG Maker MZ project.
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
- This script scans the project/staging directory for files not referenced in code or database entries.
- The directory used can be specified via the UI, or passed as a parameter from an external program.
- It is designed to work with the accompanying Stage_Project.py, which copies your project into a specified deployment folder
- It provides options to preview or permanently delete unused files.
- Use with caution as deleted files cannot be easily recovered. Recommeded use is in a staging directory
  just prior to using the Deployment... option in RPG Maker MZ. Don't forget to open the staging
  directory as the current project once you're done here :)
"""

# --- Find default animations defined by Visustella Battle Core plugin, if present
test_count = 0
def load_plugins_js(file_path):
    """Loads plugins.js as a plain text file and extracts animation IDs using string patterns."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        animation_ids = []

        # Define the patterns for the animation IDs
        patterns = [
            r'AttackAnimation:num.....(\d+)',
            r'CastCertain:num.....(\d+)',
            r'CastPhysical:num.....(\d+)',
            r'CastMagical:num.....(\d+)',
            r'ReflectAnimation:num.....(\d+)'
        ]

        # Extract animation IDs using regular expressions
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                for match in matches:  # Iterate through the list of matches
                    animation_ids.append(int(match))  # Append each individual match
        return animation_ids

    except Exception as e:
        print(f"Error reading or parsing {file_path}: {e}")
        return []

def load_animations_json(directory):
    """Loads the Animations.json file and returns a list of (effectName, id) tuples."""
    animations_file = os.path.join(directory, "Animations.json").replace("\\", "/")
    if os.path.exists(animations_file):
        with open(animations_file, 'r', encoding='utf-8') as f:
            animations_data = json.load(f)
            return [(item['effectName'], item['id']) for item in animations_data if item is not None]
    return []

def extract_key_value(data, key):
    """Recursively extracts the value associated with a given key from a nested dict or list."""
    if isinstance(data, dict):
        for k, v in data.items():
            if k == key:
                return v
            elif isinstance(v, (dict, list)):
                result = extract_key_value(v, key)
                if result is not None:
                    return result
    elif isinstance(data, list):
        for item in data:
            result = extract_key_value(item, key)
            if result is not None:
                return result
    return None

def search_content_for_file(content, source_file, target_file):
    """
    Searches the content of a file for references to another file.

    Handles different file types and search patterns.
    """
    if source_file.endswith(".efkefc"):
        if target_file.endswith('.png'):
            search_file = os.path.basename(target_file)
            if search_file in content:
                return True
        else:
            return False
    else:
        base_file = os.path.basename(target_file)
        name_file = os.path.splitext(base_file)[0]
        search_patterns = [
            f'\"{name_file}\"',  # Fully quoted
            f'/{name_file}\"',  # Subdir form
            f"{name_file}\\",  # Trailing Backslash
            base_file  # Exact match
        ]
        for pattern in search_patterns:
            if pattern in content:
                return True
        return False

def get_content_from_file(file_path):
    """Reads the content of a file and handles potential encoding issues."""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        text_content = raw_data.replace(b'\x00', b'').decode('latin1', errors='ignore')
    return text_content

def find_unused_files(directory, progress_callback):
    """
    Finds unused files in an RPG Maker MZ project directory.

    Args:
        directory: The root directory of the project.
        progress_callback: A function to update progress.

    Returns:
        A list of unused files.
    """
    files = []
    code_files = []
    animations = []
    animations_lookup = load_animations_json(os.path.join(directory, 'data'))
    test_count = 0
    for subdir, _, subfiles in os.walk(directory):
        if 'DatabaseCleanUpTool' in subdir or '.git' in subdir or '.vs' in subdir:
            continue  # Skip these subdirectories
        for file in subfiles:
            file_path = os.path.join(subdir, file).replace("\\", "/")
            # Animations and Tilesets are just used as lookups, otherwise they'd include all animations and tilesets, regardless of usage
            if file.endswith(('.js', '.json')) and 'Animations.json' not in file and 'Tilesets.json' not in file:
                code_files.append(file_path)
            elif not file.endswith("rmmzsave"):
                files.append(file_path)
    total_files = len(files)
    print(f"Searching {len(code_files)+2} base files with {total_files} potential references")
    used_files = set()

    # --- Process JSON files to find used .efkefc files ---
    print("Animation search")
    for filepath in code_files:
        try:
            if filepath.endswith('.json'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    json_content = json.load(f)
                    for item in json_content:
                        animation_id = extract_key_value(item, 'animationId')
                        if animation_id:
                            if animation_id == -1: #Normal Attack
                                continue
                            animations.append(animation_id)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

    # --- Load plugins.js ---
    print('Getting animations from plugins.js')
    plugins_file = os.path.join(directory, "js", "plugins.js").replace("\\", "/")
    if os.path.exists(plugins_file):
        animation_ids_from_plugins = load_plugins_js(plugins_file)
        animations.extend(animation_ids_from_plugins)  # Add the extracted IDs to the animations list

    # --- Process Maps to identify used tilsets -> tileset images
    print ('Processing Maps for Tilesets')
    used_tilesets = set()
    for i, filepath in enumerate(code_files):
        try:
            if filepath.endswith('.json') and 'Map' in filepath and 'MapInfo' not in filepath:
                with open(filepath, 'r', encoding='utf-8') as f:
                    map_data = json.load(f)
                    tileset_id = map_data.get('tilesetId')
                    if tileset_id is not None:
                        # Load tilesets.json
                        with open(os.path.join(directory, 'data', 'Tilesets.json'), 'r', encoding='utf-8') as f2:
                            tilesets_data = json.load(f2)
                            # Find the tileset with the matching ID
                            tileset = next(
                                (ts for ts in tilesets_data
                                 if isinstance(ts, dict) and ts.get('id') == tileset_id),
                                None)
                            if tileset:
                                # Add all tileset names from the 'tilesetNames' list
                                used_tilesets.update(tileset.get('tilesetNames', []))
                            else:
                                print(
                                    f"Warning: No tileset found with ID {tileset_id} for map {filepath}"
                                )
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

    # --- Add used tileset PNG files to used_files ---
    for tileset_name in used_tilesets:
        tileset_png = os.path.join(directory, 'img', 'tilesets', tileset_name + '.png').replace("\\", "/")
        used_files.add(tileset_png)
    
    unused_count = len(files)-len(used_files)
    test_count += 1
    progress_callback(test_count, len(code_files),len(used_files), unused_count)

# --- Process JS/JSON files for the remainder of dependencies ---
    print("Reviewing JS/JSON Files")
    for i, filepath in enumerate(code_files):
        try:
            content = get_content_from_file(filepath)
            for file in files:
                if search_content_for_file(content, filepath, file):
                    used_files.add(file)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
        unused_count = len(files)-len(used_files)
        test_count += 1
        progress_callback(test_count, len(code_files),len(used_files), unused_count)

    # --- Process Animations ---
    print("Checkin for Used Animations")
    for animation_id in animations:
        try:
            # 1. Load the animation JSON file
            with open(os.path.join(directory, 'data', 'Animations.json'), 'r', encoding='utf-8') as f:
                animations_data = json.load(f)

            # 2. Find the animation data
            animation_data = next(
                (item for item in animations_data if item and item['id'] == animation_id),
                None)
            if animation_data is None:  # Skip if animation not found
                print(f"Warning: Animation with ID {animation_id} not found.")
                continue
            # 3. Mark efkefc files as used
            for effect_name, effect_id in animations_lookup:
                if effect_id == animation_id:
                    effect_file = os.path.join(directory, 'effects', f"{effect_name}.efkefc").replace("\\", "/")
                    effect_file = effect_file.replace("\\","/")
                    used_files.add(effect_file)
                    break  # Exit the inner loop after finding a match
            # 3. Extract sound file names
            sound_files = []
            for timing in animation_data.get('soundTimings', []):
                if isinstance(timing, dict):  # Check if timing is a dictionary
                    se_data = timing['se']
                    se = se_data['name']
                    sound_files.append(se)
                elif isinstance(se,str):
                    sound_files.append(se)
                elif isinstance(timing, list):  # If timing is a list, iterate over it
                    for subtiming in timing:
                        if isinstance(subtiming, dict):
                            if isinstance(timing.get('se'), dict):  # Check if 'se' is a dictionary within 'timing'
                                for key, value in timing['se'].items():
                                    if key == 'name':
                                        sound_files.append(value)
                            else:
                                print(f'se is not a dict: {se}')  # Debug print for non-dictionary se
                else:
                    print('Timing data is something else')
            # 4. Add sound files to used_files
            for sound_file in sound_files:
                audio_file = os.path.join(directory, 'audio', 'se', sound_file + '.ogg').replace("\\", "/")
                used_files.add(audio_file)

        except Exception as e:
            print(f"Error processing animation {animation_id}: {e}")
    test_count += 1
    unused_count = len(files)-len(used_files)
    progress_callback(test_count, len(code_files),len(used_files), unused_count)
    # --- Now that we have our used efkefc, process them looking for used images ---
    for i, effect_file in enumerate(used_files.copy()):  # Iterate over a copy to avoid modification issues
        if effect_file.endswith('.efkefc'):
            try:
                content = get_content_from_file(effect_file)
                for file in files:
                    if file.endswith('.png') and search_content_for_file(content, effect_file, file):
                        used_files.add(file)
            except Exception as e:
                print(f"Error reading {effect_file}: {e}")

    unused_files = [file for file in files if file not in used_files]
    files.sort()
    return unused_files

def main(staging_path):
    def select_directory(directory):
        print(f'Using directory: {directory}')
        if directory == '':
            directory = filedialog.askdirectory()
        progress['value'] = 0
        delete_progress['value'] = 0
        output_text.delete(1.0, tk.END)
        thread = Thread(target=find_and_display_unused_files, args=(directory,))
        thread.start()

    def find_and_display_unused_files(directory):
        unused_files = find_unused_files(directory, update_progress)
        output_text.insert(tk.END, '\n'.join(unused_files))
        progress['value'] = 100
        if unused_files:
            delete_button.pack(pady=5)

    def prompt_delete():
        unused_files = output_text.get(1.0, tk.END).strip().split('\n')
        result = messagebox.askyesno("Delete Files", "Do you want to delete the unused files?")
        if result:
            total_files = len(unused_files)
            print(f'Deleting {total_files} unused files')
            thread = Thread(target=delete_unused_files, args=(unused_files))
            thread.start()

    def delete_unused_files(unused_files):
        for i, file in enumerate(unused_files):
            try:
                os.remove(file)
                output_text.insert(tk.END,file)
                app.after(100, update_delete_progress, i + 1, unused_files)
            except Exception as e:
                print(f"Error deleting {file}: {e}")
        app.after(100, deletion_complete)

    def update_progress(test_count, code_files, used_files, unused_count):
        code_files += 2
        # Calculate the percentage and update the progress bar
        percentage = (test_count / code_files) * 100
        app.after(0, lambda: progress.config(value=percentage))  # Use config(value=...)
        app.after(0, lambda: status_label.config(
            text=f"Files Evaluated: {test_count}/{code_files}, "
                 f"Unused/Used Files: {unused_count+1}/{used_files+code_files+1}"
        )) 

    def update_delete_progress(count, unused_files):
        delete_progress['value'] = (count / unused_files) * 100
        status_label2.config(text=f'Files Deleted: {count}/{unused_files}')
        app.update_idletasks()

    def deletion_complete():
        output_text.insert(tk.END, "\n\nUnused files have been deleted.")
        delete_progress['value'] = 100
        delete_button.pack_forget()
        app.update_idletasks()

    app = tk.Tk()
    app.title("RPG Maker MZ Delete Unused Files")

    frame = tk.Frame(app)
    frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    select_button = tk.Button(frame, text="Select Directory", command=lambda: select_directory(''))
    select_button.pack()

    progress = ttk.Progressbar(frame, length=400, mode='determinate')
    progress.pack(pady=10, fill=tk.X)

    status_label = tk.Label(frame, text="Files Evaluated: 0, Unused/Unused Files: 0/0")
    status_label.pack(pady=5)

    delete_progress = ttk.Progressbar(frame, length=400, mode='determinate')
    delete_progress.pack(pady=10, fill=tk.X)

    status_label2 = tk.Label(frame, text="Files Deleted: 0/0")
    status_label2.pack(pady=5)

    output_frame = tk.Frame(frame)
    output_frame.pack(pady=10, fill=tk.BOTH, expand=True)

    scrollbar = tk.Scrollbar(output_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    output_text = tk.Text(output_frame, height=20, width=50, yscrollcommand=scrollbar.set)
    output_text.pack(pady=10, fill=tk.BOTH, expand=True)

    scrollbar.config(command=output_text.yview)

    delete_button = tk.Button(frame, text="Delete Unused Files", command=prompt_delete)

    app.geometry("1200x800")

    
    print(f'Staging path received: {staging_path}')
    if staging_path == '':
        app.mainloop()
    else:
        # we don't need the selection button, because we were passed the val as a parameter
        select_button.pack_forget()
        # Start the processing in a separate thread to keep the UI responsive
        thread = Thread(target=lambda: select_directory(staging_path))
        thread.start()
        app.mainloop()  # Start the mainloop to handle UI events
    

if __name__ == "__main__":
    staging_path = ''
    if len(sys.argv) > 1:
        staging_path = sys.argv[1]
    main(staging_path)

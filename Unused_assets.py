from email.mime import base
from inspect import _empty
import os
import tkinter as tk
import json
import sys
import re
from tkinter import ttk, filedialog, messagebox
from threading import Thread
from unittest.util import sorted_list_difference

"""
Filename: Unused_assets
.py

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



cached_json = {}
app = tk.Tk()
app.title("RPG Maker MZ Delete Unused Files")
unused_files = []
test_count = 0
files = set()
used_files = set()
code_files = set()
animations = set()

# --- Find default animations defined by Visustella Battle Core plugin, if present
def get_animation_ids(file_path):
    """Loads plugins.js as a plain text file and extracts animation IDs using string patterns."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        animation_ids = set()

        # Define the patterns for the animation IDs
        patterns = [
            re.compile(r'AttackAnimation:num.....(\d+)'),
            re.compile(r'CastCertain:num.....(\d+)'),
            re.compile(r'CastPhysical:num.....(\d+)'),
            re.compile(r'CastMagical:num.....(\d+)'),
            re.compile(r'ReflectAnimation:num.....(\d+)')
        ]
        
        # Extract animation IDs using above regular expressions
        for pattern in patterns:
            matches = pattern.findall(content)
            if matches:
                for match in matches:
                    animation_ids.add(int(match))
        return animation_ids

    except Exception as e:
        print(f"Error reading or parsing {file_path}: {e}")
        return ()

def load_animations_json(directory):
    """Loads the Animations.json file and returns a list of (effectName, id) tuples."""
    animations_file = os.path.join(directory, "Animations.json").replace("\\", "/")
    if os.path.exists(animations_file):
        animations_data = load_cached_json(animations_file)
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
    Searches the content of the specified source for references to another file.

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

def load_cached_json(file_path):
    """Loads a JSON file and caches it for future use."""
    if file_path not in cached_json:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                cached_json[file_path] = json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            cached_json[file_path] = None
    return cached_json[file_path]

def extract_png_filenames(efkefc_path):
    with open(efkefc_path, "rb") as f:
        binary_data = f.read()

    # Extract potential filenames
    ascii_text = re.findall(rb'[ -~]{4,}', binary_data)  # ASCII text
    utf16_text = re.findall(rb'(?:[\x20-\x7E]\x00){4,}', binary_data)  # UTF-16 text

    # Decode extracted text
    ascii_strings = [s.decode(errors="ignore") for s in ascii_text]
    utf16_strings = [s.decode("utf-16le", errors="ignore") for s in utf16_text]

    # Merge and filter for PNGs
    potential_pngs = sorted(set(ascii_strings + utf16_strings))
    png_files = [s for s in potential_pngs if s.lower().endswith(".png")]

    return png_files

def find_unused_files(directory, output_text, progress_callback):
    """
    Finds unused files in an RPG Maker MZ project directory.

    Args:
        directory: The root directory of the project.
        progress_callback: A function to update progress.

    Returns:
        A list of unused files.
    """
    global test_count
    global files
    global used_files
    global code_files
    global animations
    file_references = {}
    used_references = {}

    animations_lookup = load_animations_json(os.path.join(directory, 'data'))
    output_text.insert(tk.END, "Cataloguing Files\n")
    for subdir, _, subfiles in os.walk(directory):
        if 'DatabaseCleanUpTool' in subdir:
            continue  # Don't include the DatabaseCleanUpTool directory
        # Assumes any file starting with a '.' is generated by external tools for their own use, and are not part of the project
        file_references['root'] = set()
        for file in subfiles:
            file_path = os.path.join(subdir, file).replace("\\", "/")
            # Keep the root directory files; process js and json along with rest of the code files
            if subdir == directory and not file.endswith(('.js','.json')):
                # We know that all of the files in the base directory are used, so we can skip them
                used_files.add(file_path)
                file_references['root'].add(file_path)
                if file_path not in used_references:
                    used_references[file_path] = set()
                used_references[file_path].add('root')
                continue
            # Animations and Tilesets are just used as lookups, otherwise they'd include all animations and tilesets, regardless of usage
            if file.endswith(('.js', '.json')) and 'Animations.json' not in file and 'Tilesets.json' not in file:
                code_files.add(file_path)
            elif not file.endswith("rmmzsave"):
                files.add(file_path)
    total_files = len(files)
    output_text.insert(tk.END, f"Searching {len(code_files)+2} core files with {total_files} potential references\n")
    
    # --- Process JSON files to find used .efkefc files ---
    output_text.insert(tk.END, "Processing JSON files for used animations\n")
    for i, filepath in enumerate(code_files):
        try:
            if filepath.endswith('.json'):
                json_content = load_cached_json(filepath)
                for item in json_content:
                    animation_id = extract_key_value(item, 'animationId')
                    if animation_id:
                        if animation_id == -1: #Normal Attack
                            continue
                        animations.add(animation_id)
        except Exception as e:
            print(f"Error reading {filepath} while processing JSON files for used animations: {e}")
    test_count += 1
    progress_callback(len(code_files),len(used_files), len(files))

    # --- Load plugins.js ---
    output_text.insert(tk.END, "Getting animations from plugins.js\n")
    plugins_file = os.path.join(directory, "js", "plugins.js").replace("\\", "/")
    if os.path.exists(plugins_file):
        animation_ids_from_plugins = get_animation_ids(plugins_file)
        animations.update(animation_ids_from_plugins)  # Add the extracted IDs to the animations list

    # --- Process Maps to identify used tilsets -> tileset images
    output_text.insert(tk.END, "Processing Maps for required Tilesets\n")
    used_tilesets = set()
    for i, filepath in enumerate(code_files):
        file_references[filepath] = set()
        try:
            if filepath.endswith('.json') and 'Map' in filepath and 'MapInfo' not in filepath:
                map_data = load_cached_json(filepath)
                tileset_id = map_data.get('tilesetId')
                if tileset_id is not None:
                    # Load tilesets.json
                    tilesets_data = load_cached_json(os.path.join(directory, 'data', 'Tilesets.json'))
                    # Find the tileset with the matching ID
                    tileset = next(
                        (ts for ts in tilesets_data
                            if isinstance(ts, dict) and ts.get('id') == tileset_id),
                        None)
                    if tileset:
                        # Add all tileset names from the 'tilesetNames' list
                        used_tilesets.update(tileset.get('tilesetNames', []))
                        # This is a set, so need to add the list as a tuple to avoid unhashable type error
                        file_references[filepath].add(tuple(tileset.get('tilesetNames',[])))
                        for tileset_name in tileset.get('tilesetNames',):
                            if tileset_name == '':
                                print(f"Warning: Tileset name is empty")
                            else:
                                if tileset_name not in used_references:
                                    used_references[tileset_name] = set()
                                used_references[tileset_name].add(filepath)
                    else:
                        print(
                            f"Warning: No tileset found with ID {tileset_id} for map {filepath}"
                        )
        except Exception as e:
            print(f"Error reading Map {filepath}: {e}")
    test_count += 1
    progress_callback(len(code_files),len(used_files), len(files))

    # --- Add used tileset PNG files to used_files ---
    for tileset_name in used_tilesets:
        tileset_png = os.path.join(directory, 'img', 'tilesets', tileset_name + '.png').replace("\\", "/")
        used_files.add(tileset_png)
        if tileset_png in files:
            files.remove(tileset_png)
    test_count += 1
    progress_callback(len(code_files),len(used_files), len(files))

    # --- Process JS/JSON files for the remainder of dependencies ---
    output_text.insert(tk.END, "Reviewing JS/JSON Files\n")
    for i, filepath in enumerate(code_files.copy()):
        try:
            content = get_content_from_file(filepath)
            for i, file in enumerate(files.copy()):
                if search_content_for_file(content, filepath, file):
                    used_files.add(file)
                    file_references[filepath].add(file)
                    if file not in used_references:
                        used_references[file] = set()
                    used_references[file].add(filepath)
                    if file in files:
                        files.remove(file)
                    
                    # we need to explicitly add the .info files for locale .pak files, as they don't contain any references to the .info files
                    if file.endswith('.pak'):
                        info_file = file + '.info'
                        used_files.add(info_file)
                        file_references[filepath].add(info_file)
                        if info_file not in used_references:
                            used_references[info_file] = set()
                        used_references[info_file].add(filepath)
                        if info_file in files:
                            files.remove(info_file)
        except Exception as e:
            print(f"Error reading {filepath} while processing js/json files: {e}")
        test_count += 1
        progress_callback(len(code_files),len(used_files), len(files))

    # --- Process Animations, looking for efkefc effect files, and any embedded sound effects ---
    output_text.insert(tk.END, "Checking for Used Animations\n")
    file_references['animations'] = set()
    for i, animation_id in enumerate(animations):
        try:
            # 1. Load the animation JSON file
            animations_data = load_cached_json(os.path.join(directory, 'data', 'Animations.json'))

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
                    used_files.add(effect_file)
                    file_references['animations'].add(effect_file)
                    if effect_file not in used_references:
                        used_references[file_path] = set()
                    used_references[file_path].add(os.path.join(directory, 'data', 'Animations.json'))
                    if effect_file in files:
                        files.remove(effect_file)
                    # 4. Extract sound file names
                    sound_files = set()
                    for timing in animation_data.get('soundTimings', []):
                        if isinstance(timing, dict):  # Check if timing is a dictionary
                            se_data = timing['se']
                            se = se_data['name']
                            sound_files.add(se)
                            file_references['animations'].add(se)
                            if se not in used_references:
                                used_references[se] = set()
                            used_references[se].add(os.path.join(directory, 'data', 'Animations.json'))
                        elif isinstance(se,str):
                            sound_files.add(se)
                        elif isinstance(timing, list):  # If timing is a list, iterate over it
                            for subtiming in timing:
                                if isinstance(subtiming, dict):
                                    if isinstance(timing.get('se'), dict):  # Check if 'se' is a dictionary within 'timing'
                                        for key, value in timing['se'].items():
                                            if key == 'name':
                                                sound_files.add(value)
                                                file_references['animations'].add(value)
                                                if value not in used_references:
                                                    used_references[value] = set()
                                                used_references[value].add(os.path.join(directory, 'data', 'Animations.json'))
                                    else:
                                        print(f'se is not a dict: {se}')  # Debug print for non-dictionary se
                        else:
                            print('Timing data is something else')
                    # 5. Add sound files to used_files
                    for sound_file in sound_files:
                        audio_file = os.path.join(directory, 'audio', 'se', sound_file + '.ogg').replace("\\", "/")
                        used_files.add(audio_file)
                        file_references['animations'].add(audio_file)
                        if audio_file not in used_references:
                            used_references[audio_file] = set()
                        used_references[audio_file].add(os.path.join(directory, 'data', 'Animations.json'))
                        if audio_file in files:
                            files.remove(audio_file)
                    break  # Exit the animations_lookup after finding a match
        except Exception as e:
            print(f"Error processing animation {animation_id}: {e}")
    test_count += 1
    progress_callback(len(code_files),len(used_files), len(files))

    # --- Now that we have our used efkefc from the animations and we've identified every other used file, process them looking for used images ---
    output_text.insert(tk.END, "Checking for Used Effects and Images\n")
    for i, effect_file in enumerate(used_files.copy()):  # Iterate over a copy to avoid modification issues
        if effect_file.endswith('.efkefc'):
            try:
                file_references['effect_file'] = set()
                # Parse the .efkefc file to find any referenced .png files
                png_files = extract_png_filenames(effect_file)
                for png_file in png_files:
                    full_path = os.path.join(directory, 'effects', png_file).replace("\\", "/")
                    if full_path in files:
                        used_files.add(full_path)
                        file_references['effect_file'].add(png_file)
                        if png_file not in used_references:
                            used_references[png_file] = set()
                        used_references[png_file].add(os.path.join(effect_file))
                        if file in files:
                            files.remove(full_path)
            except Exception as e:
                print(f"Error reading {effect_file} while checking for used effects and images: {e}")
        test_count += 1
        progress_callback(len(code_files),len(used_files), len(files))
    output_text.insert(tk.END, f'{len(files)} unused files remain')

    return list(sorted(files)), file_references, used_references

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

    def update_progress(code_count, used_count, unused_count):
        global test_count
        # Account for Animations and Tilesets, which are handled separately
        code_count += 2
        # Calculate the percentage and update the progress bar
        percentage = (test_count / code_count) * 100
        app.after(0, lambda: progress.config(value=percentage))
        app.after(0, lambda: status_label.config(
            text=f"Files Evaluated: {test_count}/{code_count}, "
                 f"Unused/Used Files: {unused_count}/{used_count+code_count}"
        ))

    def find_and_display_unused_files(directory):
        print(f'File name var: {show_by_filename_var.get()}')
        unused_files, references, filerefs = find_unused_files(directory, output_text, update_progress)
        if show_references_var.get():
            output_text.insert(tk.END, "\n\n--------------Used File References--------------\n")
            if show_by_filename_var.get():
                output_str = ""
                # sorted_list_difference = sorted(filerefs.items())
                sorted_list_difference = filerefs.items()
                for source_file, used_files in sorted_list_difference:
                    output_str += f"File: {source_file} Used In:\n"
                    for used_file in used_files:
                        output_str += f"  - {used_file}\n"
                output_text.insert(tk.END, output_str)
            else:
                output_str = ""
                for source_file, used_files in references.items():
                    output_str += f"Source: {source_file}\n"
                    output_str += "Used Files:\n"
                    for used_file in used_files:
                        output_str += f"  - {used_file}\n"
                output_text.insert(tk.END, output_str)
        output_text.insert(tk.END, "\n\n--------------Unused Files, Marked For Deletion--------------\n")
        output_text.insert(tk.END, '\n'.join(unused_files))
        progress['value'] = 100
        if unused_files:
            delete_button.pack(pady=5)

    def prompt_delete():
        output_files = output_text.get(1.0, tk.END).strip().split('\n')
        result = messagebox.askyesno("Delete Files", "Do you want to delete the unused files?")
        if result:
            print(f'Deleting {len(files)} unused files')
            thread = Thread(target=delete_unused_files, args=[output_files])
            thread.start()

    def delete_unused_files(files):
        for i, file in enumerate(files):
            try:
                os.remove(file)
                output_text.insert(tk.END,file)
                app.after(100, update_delete_progress, i + 1, files, used_files)
            except Exception as e:
                print(f"Error deleting {file}: {e}")
        app.after(100, deletion_complete)

    def update_delete_progress(count, files, used_files):
        delete_progress['value'] = (count / (len(files)+len(used_files))) * 100
        status_label2.config(text=f'Files Deleted: {count}/{len(files)}')
        app.update_idletasks()

    def deletion_complete():
        output_text.delete(1.0, tk.END)
        output_text.insert(tk.END, "\n\nUnused files have been deleted.")
        delete_progress['value'] = 100
        delete_button.pack_forget()
        app.update_idletasks()
        app.destroy()

    frame = tk.Frame(app)
    frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    select_button = tk.Button(frame, text="Select Directory of RPG Maker Project", command=lambda: select_directory(''))
    select_button.pack()

    show_references_var = tk.BooleanVar(value=False)  # Variable to store checkbox state
    show_references_checkbox = tk.Checkbutton(frame, text="Show Used File References", variable=show_references_var)
    show_references_checkbox.pack(pady=5)
    
    show_by_filename_var = tk.BooleanVar(value=False)
    show_by_filename_checkbox = tk.Checkbutton(frame, text="Order by filename used, not by where used", variable=show_by_filename_var)
    show_by_filename_checkbox.pack(pady=5)

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
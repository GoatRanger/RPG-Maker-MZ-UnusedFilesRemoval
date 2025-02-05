from email.mime import base
from inspect import _empty
from msilib import Directory
import os
import tkinter as tk
import json
import sys
import re
from tkinter import ttk, filedialog, messagebox
from threading import Thread, main_thread
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
- Use with caution. Recommended use is in a staging directory after using the Deployment... option in RPG Maker MZ.
- Only tested with a Windows deployment. May not work with other operating systems.
"""

cached_json = {}  # Cache for JSON files to avoid re-reading them
app = tk.Tk()
app.title("RPG Maker MZ Delete Unused Files")
unused_files = []
test_count = 0
unused_files = set()
used_files = set()
code_files = set()
animations = set()

def get_used_plugins(directory):
    """
    Finds and returns a list of used plugins in an RPG Maker MZ project.

    This function reads the 'plugins.js' file in the specified directory
    and extracts the names of the used plugins. It always includes 'plugins.js'
    and 'main.js' as they are essential for the project and include the names
    for any plugins, including the RMMZ Core plugins in main.js.

    Args:
        directory: The directory containing the RPG Maker MZ project files.

    Returns:
        A list of used plugin filenames.
    """
    used_plugins = []
    plugins_file = os.path.join(directory, "js", "plugins.js").replace("\\", "/")
    if os.path.exists(plugins_file):
        try:
            # Read the content of plugins.js
            with open(plugins_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract the valid JSON string using string manipulation
            start_index = content.index('[')  # Find the start of the JSON array
            end_index = content.rindex(']') + 1  # Find the end of the JSON array
            json_string = content[start_index:end_index]

            # Load the JSON string as a JSON object
            plugins_data = json.loads(json_string)

            # Extract plugin names from the JSON data
            for plugin in plugins_data:
                used_plugins.append(f"plugins/{plugin['name']}.js")
            print(f"Found {len(used_plugins)} plugins in plugins.js")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error loading plugins.js: {e}")
            #
    used_plugins.append('plugins.js')  # Always include plugins.js
    used_plugins.append('main.js')  # Always include main.js)
    # --- Process main.js for core references ---
    main_file = os.path.join(directory, 'js', 'main.js').replace("\\", "/")
    main_content = get_content_from_file(main_file)
    main_files = re.findall(r'(?<=\'|")([^\'"]+\.(?:js|json))\"',main_content)
    for file in main_files:
        # We prepend 'js/' to the file name later to match the directory structure
        if file.startswith('js/'):
            file = file[3:]
        used_plugins.append(file)
    return used_plugins

# --- Find default animations defined by Visustella Battle Core plugin, if present
def get_animation_ids(file_path):
    """
    Extracts animation IDs from a file.

    This function reads the content of the specified file, searches for
    animation IDs using predefined regular expression patterns, and returns
    a set of unique animation IDs found in the file.

    Args:
        file_path: The path to the file to extract animation IDs from.

    Returns:
        A set of unique animation IDs found in the file.
    """
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
    """
    Loads animation data from Animations.json.

    This function reads the `Animations.json` and extracts relevant 
    animation data, returning it as a list of tuples. Each tuple 
    contains the animation's effect name and its corresponding ID.

    Args:
        directory: The directory containing the `Animations.json` file.

    Returns:
        A list of tuples, each containing an animation's effect name and ID.
    """
    animations_file = os.path.join(directory, "Animations.json").replace("\\", "/")
    if os.path.exists(animations_file):
        animations_data = load_cached_json(animations_file)
        return [(item['effectName'], item['id']) for item in animations_data if item is not None]
    return []

def extract_key_value(data, key):
    """
    Recursively extracts values associated with a key from nested data.

    This function searches a nested dictionary or list for a specific key
    and returns the corresponding value. It handles nested structures by
    recursively searching through dictionaries and lists within the data.

    Args:
        data: The nested dictionary or list to search.
        key: The key to search for.

    Returns:
        The value associated with the key, or None if the key is not found.
    """
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
    Checks if a file references another file.

    This function searches the content of a source file for any references
    to a target file. It handles different file types and search patterns
    to accurately identify file references.

    Args:
        content: The content of the source file.
        source_file: The path to the source file.
        target_file: The path to the target file.

    Returns:
        True if the source file references the target file, False otherwise.
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
            f'\"{name_file}\"',  # Fully quoted, without file extension
            f'/{name_file}',  # Subdir form, without file extension
            f"{name_file}\\",  # Trailing Backslash, without file extension
            base_file  # Exact match with file extension
        ]
        for pattern in search_patterns:
            if pattern in content:
                return True
        return False

def get_content_from_file(file_path):
    """
    Reads and decodes the content of a file.

    This function reads the raw data from a file in binary mode,
    removes any null bytes, and then decodes the data using
    Latin-1 encoding (with error handling) to ensure proper
    text extraction.

    Args:
        file_path: The path to the file to read.

    Returns:
        The decoded text content of the file.
    """
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        text_content = raw_data.replace(b'\x00', b'').decode('latin1', errors='ignore')
    return text_content

def load_cached_json(file_path):
    """
    Loads and caches JSON files for reuse.

    This function loads a JSON file and stores it in a cache
    to avoid redundant file reads. If the file has already been
    loaded, it retrieves the data from the cache.

    Args:
        file_path: The path to the JSON file.

    Returns:
        The data loaded from the JSON file.
    """
    if file_path not in cached_json:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                cached_json[file_path] = json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            cached_json[file_path] = None
    return cached_json[file_path]

def extract_png_filenames(efkefc_path):
    """
    Extracts PNG filenames from an efkefc file.

    This function reads the binary data of an efkefc file, extracts potential
    filenames based on ASCII and UTF-16 encoding patterns, and returns a list
    of PNG filenames found within the file.

    Args:
        efkefc_path: The path to the efkefc file.

    Returns:
        A list of PNG filenames.
    """
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

def find_unused_files(test_count, directory, output_text, progress_callback):
    """
    Finds unused files in an RPG Maker MZ project directory.

    Args:
        test_count: A counter for tracking the progress of the file analysis.
        directory: The root directory of the project.
        output_text: The text box to display the output.
        progress_callback: A function to update progress.

    Returns:
        A tuple containing:
        - A list of unused files.
        - A set of used files.
        - A dictionary of file references.
        - A dictionary of files and where they are used.
    """
    global unused_files
    global used_files
    global code_files
    global animations
    file_references = {}
    files_used_in = {}

    animations_lookup = load_animations_json(os.path.join(directory, 'data'))
    output_text.insert(tk.END, "Cataloguing Files\n")

    # Build initial set of unused files, excluding the root directory,
    # the 'DatabaseCleanUpTool' directory, and any files starting 
    # with '.' (assumed to be generated by external tools).
    # Also populate the file_references dictionary with root files.
    for subdir, _, subfiles in os.walk(directory):
        if 'DatabaseCleanUpTool' in subdir:
            continue  # Don't include the DatabaseCleanUpTool directory
        # Assumes any file starting with a '.' is generated by external tools for their own use, and are not part of the project
        file_references['root'] = set()
        for file in subfiles:
            file_path = os.path.join(subdir, file).replace("\\", "/")
            # Keep the root directory files; process js and json along with rest of the code files
            if subdir == directory:
                # We know that all of the files in the base directory are used, so we can skip them
                used_files.add(file_path)
                file_references['root'].add(file_path)
                if file_path not in files_used_in:
                    files_used_in[file_path] = set()
                files_used_in[file_path].add('root')
                continue
            if not file.endswith("rmmzsave"):
                unused_files.add(file_path)
    total_files = len(unused_files)

    # --- Process plugins.js for used plugins ---
    output_text.insert(tk.END, "Processing plugins.js for used plugins\n")
    used_plugins = get_used_plugins(directory)
    # Add the plugin .js files to used_files and code_files
    for plugin_name in used_plugins:
        plugin_file = os.path.join(directory, 'js', plugin_name).replace("\\", "/")
        code_files.add(plugin_file)
        used_files.add(plugin_file)
        if plugin_file not in file_references:
            file_references[plugin_file] = set()
        file_references[plugin_file].add('.')
        if plugin_file in unused_files:
            unused_files.remove(plugin_file)
        if plugin_file not in files_used_in:
            files_used_in[plugin_file] = set()
        files_used_in[plugin_file].add('.')
    progress_callback(test_count, len(code_files),len(used_files), len(unused_files))

    # --- Find all js/json in data directory ---
    for subdir, _, subfiles in os.walk(os.path.join(directory, 'data')):
        for file in subfiles:
            if file.endswith('.js') or file.endswith('.json'):
                file_path = os.path.join(subdir, file).replace("\\", "/")
                code_files.add(file_path)
                used_files.add(file_path)
                if file_path not in file_references:
                    file_references[file_path] = set()
                file_references[file_path].add('.')
                if file_path in unused_files:
                    unused_files.remove(file_path)
                if file_path not in files_used_in:
                    files_used_in[file_path] = set()
                files_used_in[file_path].add('.')
                if file_path in unused_files:
                    unused_files.remove(file_path)
        
    output_text.insert(tk.END, f"Searching {len(code_files)} core files with {total_files} potential references\n")
    # --- Process main.js for effekseerWasmUrl plugin ---
    # if we have the effekseerWasmUrl plugin, we need to add it to the used files
    main_file = os.path.join(directory, 'js', 'main.js').replace("\\", "/")
    main_content = get_content_from_file(main_file)
    # If the 'effekseerWasmUrl' plugin is present in main.js,
    # add it to the used_files set and update tracking dictionaries.
    if ('effekseerWasmUrl' in main_content):
        used_files.add('effekseerWasmUrl')
        if 'effekseerWasmUrl' in unused_files:
            unused_files.remove('effekseerWasmUrl')
            if 'effekseerWasmUrl' not in files_used_in:
                files_used_in['effekseerWasmUrl'] = set()
            files_used_in['effekseerWasmUrl'].add(main_file)

    # Iterate through JSON files to find animation IDs and add them
    # to the `animations` set for later processing.
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
    progress_callback(test_count, len(code_files),len(used_files), len(unused_files))

    # --- Load plugins.js, get referenced animation files ---
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
                    else:
                        print(
                            f"Warning: No tileset found with ID {tileset_id} for map {filepath}"
                        )
        except Exception as e:
            print(f"Error reading Map {filepath}: {e}")
    progress_callback(test_count, len(code_files),len(used_files), len(unused_files))

    # --- Add used tileset PNG files to used_files ---
    for tileset_name in used_tilesets:
        tileset_png = os.path.join(directory, 'img', 'tilesets', tileset_name + '.png').replace("\\", "/")
        used_files.add(tileset_png)
        if tileset_png in unused_files:
            unused_files.remove(tileset_png)
        if tileset_name == '':
            print(f"Warning: Tileset name is empty")
        else:
            if tileset_png not in files_used_in:
                files_used_in[tileset_png] = set()
            files_used_in[tileset_png].add(filepath)
    progress_callback(test_count, len(code_files),len(used_files), len(unused_files))

    # --- Process JS/JSON files for the remainder of dependencies ---
    output_text.insert(tk.END, "Reviewing JS/JSON Files\n")
    outputCount = 0
    for i, filepath in enumerate(code_files.copy()):
        try:
            content = get_content_from_file(filepath)
            for i, file in enumerate(unused_files.copy()):
                if search_content_for_file(content, filepath, file):
                    if 'GroupB_00' in file:
                        print(f"Found {file} in {filepath}")
                    used_files.add(file)
                    file_references[filepath].add(file)
                    if file not in files_used_in:
                        files_used_in[file] = set()
                    files_used_in[file].add(filepath)
                    if file in unused_files:
                        outputCount += 1
                        unused_files.remove(file)
                    # we need to explicitly add the .info files for locale .pak files, as they don't contain any references to the .info files
                    if file.endswith('.pak'):
                        info_file = file + '.info'
                        used_files.add(info_file)
                        file_references[filepath].add(info_file)
                        if info_file not in files_used_in:
                            files_used_in[info_file] = set()
                        files_used_in[info_file].add(filepath)
                        if info_file in unused_files:
                            unused_files.remove(info_file)
            # print(f"----------------------- Processed {filepath} with {outputCount} new references ----------------------")
            outputCount = 0

        except Exception as e:
            print(f"Error reading {filepath} while processing js/json files: {e}")
        test_count += 1
        progress_callback(test_count, len(code_files),len(used_files), len(unused_files))

    # Process animations to identify used.efkefc files and any
    # embedded sound effects (.ogg files).
    output_text.insert(tk.END, "Checking for Used Animations\n")
    file_references['animations'] = set()
    for i, animation_id in enumerate(animations):
        #try:
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
                    if effect_file not in files_used_in:
                        files_used_in[file_path] = set()
                    files_used_in[file_path].add(os.path.join(directory, 'data', 'Animations.json').replace("\\", "/"))
                    if effect_file in unused_files:
                        unused_files.remove(effect_file)
                    # 4. Extract sound file names
                    sound_files = set()
                    for timing in animation_data.get('soundTimings', []):
                        if isinstance(timing, dict):  # Check if timing is a dictionary
                            se_data = timing['se']
                            se = se_data['name']
                            sound_files.add(se)
                            file_references['animations'].add(se)
                            if se not in files_used_in:
                                files_used_in[se] = set()
                            files_used_in[se].add(os.path.join(directory, 'data', 'Animations.json'))
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
                                    else:
                                        print(f'se is not a dict: {se}')  # Debug print for non-dictionary se
                        else:
                            print('Timing data is something else')
                    # 5. Add sound files to used_files
                    for sound_file in sound_files:
                        audio_file = os.path.join(directory, 'audio', 'se', sound_file + '.ogg').replace("\\", "/")
                        used_files.add(audio_file)
                        file_references['animations'].add(audio_file)
                        if audio_file not in files_used_in:
                            files_used_in[audio_file] = set()
                        files_used_in[audio_file].add(os.path.join(directory, 'data', 'Animations.json'))
                        if audio_file in unused_files:
                            unused_files.remove(audio_file)
                    break  # Exit the animations_lookup after finding a match
        #except Exception as e:
         #   print(f"Error processing animation {animation_id}: {e}")
    progress_callback(test_count, len(code_files),len(used_files), len(unused_files))

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
                    if full_path in unused_files:
                        used_files.add(full_path)
                        file_references['effect_file'].add(png_file)
                        if png_file not in files_used_in:
                            files_used_in[png_file] = set()
                        files_used_in[png_file].add(os.path.join(effect_file))
                        if file in unused_files:
                            unused_files.remove(full_path)
            except Exception as e:
                print(f"Error reading {effect_file} while checking for used effects and images: {e}")
    progress_callback(test_count, len(code_files),len(used_files), len(unused_files))
    output_text.insert(tk.END, f'{len(unused_files)} unused files remain')

    return list(sorted(unused_files)), used_files, file_references, files_used_in

def main(staging_path):
    # --- GUI Event Handler Functions ---
    selected_directory = tk.StringVar(value="")
    def select_directory():
        staging_path = filedialog.askdirectory()
        selected_directory.set(staging_path)
        selected_dir.config(text=f"Selected Directory: {staging_path}")
        print(f'Using directory: {staging_path}')
        
    def run_finder():
        global unused_files
        global test_count
        global used_files
        global code_files
        global animations
        progress['value'] = 0
        delete_progress['value'] = 0
        unused_files = []
        test_count = 0
        unused_files = set()
        used_files = set()
        code_files = set()
        animations = set()
        output_text.delete(1.0, tk.END)
        staging_path = selected_directory.get()
        print(f'Running unused file finder on {staging_path}')
        thread = Thread(target=find_and_display_unused_files, args=(staging_path,))
        thread.start()

    def update_progress(test_count, code_count, used_count, unused_count):
        # Calculate the percentage and update the progress bar
        percentage = (test_count / code_count) * 100
        app.after(0, lambda: progress.config(value=percentage))
        app.after(0, lambda: status_label.config(
            text=f"Files Evaluated: {test_count}/{code_count}, "
                 f"Unused/Used Files: {unused_count}/{used_count+code_count}"
        ))

    def find_and_display_unused_files(directory):
        print(f'Finding unused files in {directory}')
        test_count = 0
        unused_files, used_files, references, where_used = find_unused_files(test_count, directory, output_text, update_progress)
        if show_references_var.get():
            output_text.insert(tk.END, "\n\n--------------Used File References--------------\n")
            if show_by_filename_var.get():
                output_str = ""
                sorted_list_difference = sorted(where_used.items())
                #sorted_list_difference = where_used.items()
                for source_file, used_files in sorted_list_difference:
                    output_str += f"File: {source_file} Used In:\n"
                    # Sort used_files, handling tuples and strings separately
                    sorted_used_files = sorted([f for f in used_files if isinstance(f, str)])  # Sort strings
                    sorted_tuples = sorted([f for f in used_files if isinstance(f, tuple)])  # Sort tuples

                    # Add "Tilesets: " prefix to each tuple
                    sorted_used_files += [f"Tilesets: {t}" for t in sorted_tuples]
                    #output_str += f"  - {sorted_used_files}\n"
                    for used_file in sorted_used_files:
                        output_str += f"  - {used_file}\n"
                output_text.insert(tk.END, output_str)
            else:
                output_str = ""
                for source_file, used_files in sorted(references.items(), key=lambda item: item):
                    output_str += f"Files Used In: {source_file}\n"
                    # Sort used_files, handling tuples and strings separately
                    sorted_used_files = sorted([f for f in used_files if isinstance(f, str)])  # Sort strings
                    sorted_tuples = sorted([f for f in used_files if isinstance(f, tuple)])  # Sort tuples
                    # Add "Tilesets: " prefix to each tuple
                    sorted_used_files += [f"Tilesets: {t}" for t in sorted_tuples]

                    #output_str += f"  - {sorted_used_files}\n"
                    for used_file in sorted_used_files:
                        output_str += f"  - {used_file}\n"
                output_text.insert(tk.END, output_str)
        output_text.insert(tk.END, "\n\n--------------Unused Files, Marked For Deletion--------------\n")
        output_text.insert(tk.END, '\n'.join(unused_files))
        progress['value'] = 100
        if unused_files:
            delete_button.pack(pady=5)

    def prompt_delete():
        result = messagebox.askyesno("Delete Files", "Do you want to delete the unused files?")
        if result:
            print(f'Deleting {len(unused_files)} unused files')
            thread = Thread(target=delete_unused_files, args=[unused_files])
            thread.start()

    def delete_unused_files(files):
        for i, file in enumerate(files):
            if 'GroupB_00' in file:
                print(f"Deleting {file}")
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

    # --- GUI Element Definitions ---
    def deletion_complete():
        output_text.delete(1.0, tk.END)
        output_text.insert(tk.END, "\n\nUnused files have been deleted.")
        delete_progress['value'] = 100
        delete_button.pack_forget()
        app.update_idletasks()
        app.destroy()

    frame = tk.Frame(app)
    frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True) 

    select_button = tk.Button(frame, text="Select Directory of RPG Maker Project", command=lambda: select_directory())
    select_button.pack()

    selected_dir = tk.Label(frame, text="Selected Directory: ")
    selected_dir.pack(pady=5)

    show_references_var = tk.BooleanVar(value=False)  # Variable to store checkbox state
    show_references_checkbox = tk.Checkbutton(frame, text="Show Used File References", variable=show_references_var)
    show_references_checkbox.pack(pady=5)
    
    show_by_filename_var = tk.BooleanVar(value=False)
    show_by_filename_checkbox = tk.Checkbutton(frame, text="Order by filename used, not by where used", variable=show_by_filename_var)
    show_by_filename_checkbox.pack(pady=5)

    run_button = tk.Button(frame, text="Find Unused Files", command=run_finder)
    run_button.pack(pady=5)

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
        selected_dir.config(text=f"Selected Directory: {staging_path}")
        selected_directory = tk.StringVar(value=staging_path)
        app.mainloop()  # Start the mainloop to handle UI events
    

if __name__ == "__main__":
    staging_path = ''
    if len(sys.argv) > 1:
        staging_path = sys.argv[1]
    main(staging_path)
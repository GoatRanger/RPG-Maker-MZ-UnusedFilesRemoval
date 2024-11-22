# RPG Maker MZ Unused Asset Tools

This repository contains two Python scripts designed to help RPG Maker MZ developers manage and clean up unused assets in their projects:

## Unused_assets_Gem.py
## Stage_Project.py

These scripts copy your RPG Maker MZ project directory and scans it to identify unused files (images, audio, etc.) that are not referenced in your game's data files or code. 
It provides options to preview the list of unused files and/or permanently delete them.

**Features:**

*   Copies an RPG Maker MZ Project folder (or really any folder) to a specified Staging directory.
*   Identifies unused images, audio files, and other assets.
**  Currently assumes that all JSON files are required, so remove any unused plugins from your plugin folder prior to use
**  Doesn't handle dynamic filenames in scripts, so make sure you add those using MaterialBase or some other method of directly specifying assets required
*   Handles various RPG Maker MZ file types (JSON, JS, EFKEFC, etc.).
*   Provides a preview of unused files before deletion.
*   Option to permanently delete unused files.

**Usage:**

1.  Place `Stage_Project.py` and `Unused_assets_Gem.py` in the same directory, doesn't matter where.
2.  Run the script from the command line: `python Stage_Project.py`. Optionally run `python Unused_assets_Gem.py` to remove unused files if you already have a project staging directory
3.  Follow the on-screen prompts to select your project directory and choose whether to preview or delete unused files.

## Stage_Project.py

This script automates the process of staging your RPG Maker MZ project for deployment. It can perform various tasks, including:

*   Copying your project to a new staging directory.
*   Running `Unused_assets_Gem.py` to remove unused files.

**Features:**

*   Automates project staging.
*   Integrates with `Unused_assets_Gem.py` for asset cleanup.
*   Can be customized for your specific deployment needs.

**Usage:**

1.  Place `Stage_Project.py` in the same directory as `Unused_assets_Gem.py`.
2.  Run the script from the command line: `python Stage_Project.py`
3.  The script will prompt you for the source and destination directories and perform the staging process.
4.  As written it always runs `Unused_assets_Gem.py`. This is a non-destructive scan for unused files. You must manually decide to delete them. 

## Unused_assets_Gem.py

This script automates the process of removing unreferenced files from your RPG Maker MZ project prior to deployment. Useful either for web deployment on
a platform like itch.io, or just reducing the overall footprint of your project. You might have 1000+ unused files if you start from a full RPG Maker MZ template.
This program performs various tasks, including:

*   Scans the specified project for files that are not referenced. Looks at js, json, efkefc for file references. 
*   Does a deep-dive on Automations.json, plugins.js, and all used efkefc files.

**Features:**

*   Automates unused file detection and optional deletion.
*   Integrates with `Stage_Project.py` for project staging prior to cleanup.

**Usage:**

1.  Place `Stage_Project.py` in the same directory as `Unused_assets_Gem.py`.
2.  Run the script from the command line: `python Unused_assets_Gem.py`. Note that it will also run automatically if `Stage_Project.py` is used.
3.  If run directly, will prompt you for the project's base directory. Will automatically get the directory if using `Stage_Project.py`.
4.  Perform a non-destructive scan for unused files, listing the files it determined were unused. You must manually decide to delete them.
5.  Recommend you scan that list for files you know are required before deletion. If you need to mark some of them as used:
	a. Use MaterialBase.json from the RPG Maker MZ program's dlc folder (`RPG Maker MZ\dlc\BasicResources\plugins\official`) or
	b. Use `@requiredAssets` in any associated js plugin.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
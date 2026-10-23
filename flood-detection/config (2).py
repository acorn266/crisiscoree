"""
Shared configuration.

Each person using this toolkit needs their OWN free Google Earth Engine
project (access is tied to your Google account, it can't be shared/borrowed
between teammates).

First time you run any script here, if config.txt doesn't exist yet, you'll
be asked for your project ID once. It's then saved to config.txt so every
script (app.py, monitor_flood.py, gee_flood_detection.py) automatically uses
it after that -- no need to edit code.

Don't have a project ID yet? See "For a new teammate" in README.md.
"""

import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.txt")


def get_project_id():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            project_id = f.read().strip()
        if project_id:
            return project_id

    print("\n=== First-time setup ===")
    print("This toolkit needs your Google Earth Engine project ID.")
    print("If you don't have one yet, see 'For a new teammate' in README.md")
    print("(short version: register free at https://code.earthengine.google.com/register,")
    print("create a project, and copy the project ID from the URL/dashboard).\n")
    project_id = input("Enter your Earth Engine project ID: ").strip()

    with open(CONFIG_FILE, "w") as f:
        f.write(project_id)

    print(f"Saved to {CONFIG_FILE} -- you won't be asked again on this computer.\n")
    return project_id

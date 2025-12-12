# BlockyTK

BlockyTK is a graphical user interface (GUI) overlay for [Minescript](https://minescript.net/), allowing you to manage, configure, and run your Python automation scripts directly from within Minecraft.

## Features

*   **In-Game GUI:** A modern, dark-themed overlay (built with `customtkinter`) that sits on top of your Minecraft window.
*   **Script Manager:** Browse automatically categorized scripts found in your `minescript/scripts/` folder.
*   **One-Click Execution:** Start and stop scripts with a "Run/Stop" button.
*   **Visual Configuration:** Configure script parameters (numbers, booleans, dropdowns) using sliders and switches—no code editing required.
*   **Hotkeys:** Bind scripts to keyboard shortcuts for instant activation.
*   **Portable:** Uses a local `lib/` folder for dependencies, keeping your installation clean and self-contained.

## Installation

### Prerequisites
*   **Minecraft** with the **Minescript** mod installed.
*   **Python 3.x** installed and configured in Minescript's `config.txt`.

### Setup
1.  **Download:**
    Download this repository and place the contents into your Minescript folder.
    *   Path: `%appdata%\.minecraft\minescript\` (or your specific profile's `minescript` folder).

2.  **Install Dependencies:**
    BlockyTK relies on `customtkinter`, which is not included by default. To make installation easy and portable, we've provided a helper script.
    
    Open a terminal in your `minescript` folder and run:
    ```bash
    python install_dependencies.py
    ```
    This will install the required libraries into a local `lib/` folder, ensuring the Hub works immediately without needing to modify your global Python environment or Minescript's `PYTHONPATH`.

## Usage

1.  **Start the Hub:**
    In Minecraft, open the chat and type:
    ```
    \gui_launcher
    ```
    *Note: The first time you run this, it might take a moment to initialize.*

2.  **Toggle the Menu:**
    Once loaded, you will see a message: "BlockyTK loaded. Press R-Shift to toggle."
    Press **Right Shift** to open/close the menu.

3.  **Running Scripts:**
    *   **Browse:** Use the sidebar to find scripts by category.
    *   **Configure:** Click "Configure" to change settings (e.g., bridge material, build delay).
    *   **Run:** Click the "Run" button to start the script. The button will change to "Stop" while it is running.

4.  **Shortcuts:**
    *   Go to a script's "Configure" page.
    *   Click the **Shortcut** button.
    *   Press any key to bind that script to the key.
    *   You can now trigger that script anytime by pressing that key (even when the menu is closed).

## Writing Scripts for the Hub

To make your own scripts appear in the Hub, they must export a `UI_CONFIG` using the `ScriptUI` helper.

Here is an example using `bridge.py` (found in `scripts/bridge.py`):

1.  Create a new `.py` file in `minescript/scripts/`.
2.  Import `minescript` and `minescript_ui`.
3.  Define your UI and `run` function:

```python
import minescript
import time
import math
from minescript_ui import ScriptUI

# 1. Define UI
ui = ScriptUI("Auto Bridge", category="Travel", description="Automatically places blocks under your feet if there is air.")
ui.dropdown("material", "Material", ["stone", "cobblestone", "dirt", "oak_planks", "glass"], default="cobblestone")
ui.float("delay", "Check Delay", default=0.05, min=0.01, max=0.5)

# 2. Export Config
UI_CONFIG = ui.export()

# 3. Main Logic
def run(params, stop_event):
    mat = params['material']
    delay = params['delay']
    minescript.echo(f"🌉 Bridge Builder Active ({mat}). Walk carefully!")
    
    while not stop_event.is_set():
        px, py, pz = minescript.player_position()
        
        # Block immediately below feet
        # Use math.floor(py) - 1 for block under feet
        bx, by, bz = round(px), math.floor(py) - 1, round(pz)
        
        # "setblock x y z block keep" only places if air.
        minescript.execute(f"setblock {bx} {by} {bz} {mat} keep")
        
        if stop_event.wait(delay): break
        
    minescript.echo("🛑 Bridge Builder Stopped.")
```

## Configuration

*   **`config.txt`**: Standard Minescript configuration.
*   **`gui_config.py`**: Generated file storing your shortcuts and Hub preferences. Do not edit manually unless necessary.

## Troubleshooting

*   **"Module not found":** Run `python install_dependencies.py` again to ensure `lib/` is populated.
*   **Menu not showing:** Check the chat for errors. Ensure you are running `\gui_launcher`, not `\gui_launcher.py`.

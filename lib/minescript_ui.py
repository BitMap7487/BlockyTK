class ScriptUI:
    def __init__(self, title, category="Uncategorized", description=""):
        self.data = {
            "title": title,
            "category": category,
            "description": description,
            "controls": {}
        }

    def int(self, id, label, default=0, min=0, max=100):
        """Adds an Integer Slider."""
        self.data["controls"][id] = {
            "type": "int",
            "label": label,
            "default": default,
            "min": min,
            "max": max
        }
        return self

    def float(self, id, label, default=0.0, min=0.0, max=1.0):
        """Adds a Float Slider."""
        self.data["controls"][id] = {
            "type": "float",
            "label": label,
            "default": default,
            "min": min,
            "max": max
        }
        return self

    def bool(self, id, label, default=False):
        """Adds a Toggle Switch."""
        self.data["controls"][id] = {
            "type": "bool",
            "label": label,
            "default": default
        }
        return self

    def dropdown(self, id, label, options, default=None):
        """Adds a Dropdown Menu."""
        if default is None and options:
            default = options[0]
            
        self.data["controls"][id] = {
            "type": "dropdown",
            "label": label,
            "options": options,
            "default": default
        }
        return self
    
    def shortcut(self, key_code):
        """Sets a default shortcut key (integer keycode)."""
        self.data["shortcut_key"] = key_code
        return self

    def export(self):
        """Returns the dictionary required by the GUI Launcher."""
        return self.data

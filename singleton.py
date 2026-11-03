from settings_model import Settings

# static file that holds variables / data that are static / singleton across the app or code
SETTINGS = Settings.load()
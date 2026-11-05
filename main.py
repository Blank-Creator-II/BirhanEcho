import time
from pathlib import Path
from cardinal_system import Cardinal

if __name__ == "__main__":
    json_root_path = Path("Books", "Chemistry Grade 11")
    
    cardinal = Cardinal()
    cardinal.initialize_app_greet()
    cardinal.initialize_speech_receiver()
    #cardinal.create_audib(json_root_path)
    #cardinal.load_audib(Path("Data", f"{json_root_path}.audib"))
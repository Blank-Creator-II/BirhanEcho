import time
from pathlib import Path
from cardinal_system import Cardinal
from Processor.processor import TextbookProcessor   

if __name__ == "__main__":
    json_root_path = Path("Books", "Biology Grade 11", "json")

    processor = TextbookProcessor(Path("Test", "Biology Grade 11.pdf"))
    processor.process_textbook()    
    
    cardinal = Cardinal()
    cardinal.initialize_app_greet()
    cardinal.initialize_speech_receiver()
    cardinal.create_audib(json_root_path)
    cardinal.load_audib(Path("Data", f"{json_root_path.parent}.audib"))
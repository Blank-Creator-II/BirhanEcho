import webview
import threading
import time
import json
from cardinal_system import Cardinal

class Api:
    def pump(self, window, audio):
        last_subtitle = None
        while True:
            levels = audio.get_current_audio_levels()
            window.evaluate_js(
                "window.viz.setAudioLevels("
                f"{levels[0]:.3f},{levels[1]:.3f},{levels[2]:.3f},{levels[3]:.3f})"
            )
            subtitle = audio.subtitle
            if subtitle != last_subtitle:
                window.evaluate_js(f"window.viz.setSubtitle({json.dumps(subtitle)})")
                last_subtitle = subtitle
            time.sleep(1 / 30)

if __name__ == '__main__':
    cardinal = Cardinal()
    cardinal.initialize_app_greet()
    cardinal.initialize_speech_receiver()

    api = Api()

    # Create the native desktop window pointing to your HTML file
    window = webview.create_window(
        title="BirhanEcho",
        url='UI/index.html',
        width=1000,
        height=700,
        resizable=True,
        min_size=(800, 600)
    )

    window.events.loaded += lambda: threading.Thread(
        target=api.pump,
        args=(window, cardinal.audio_controller),
        daemon=True,
    ).start()
    webview.start(debug=False)


# if __name__ == "__main__":
#     json_root_path = Path("Books", "Biology Grade 11", "json")

#     processor = TextbookProcessor(Path("Test", "Biology Grade 11.pdf"))
#     processor.process_textbook()

#     cardinal = Cardinal()
#     cardinal.initialize_app_greet()
#     cardinal.initialize_speech_receiver()
#     cardinal.create_audib(json_root_path)
#     cardinal.load_audib(Path("Data", f"{json_root_path.parent}.audib"))

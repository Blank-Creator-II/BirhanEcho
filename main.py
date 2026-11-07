import webview
from cardinal_system import Cardinal

def initialize_cardinal():
    cardinal = Cardinal(window)

    cardinal.initialize_audio_data_sender()
    cardinal.initialize_app_greet()
    cardinal.initialize_speech_receiver()

if __name__ == '__main__':
    # Create the native desktop window pointing to your HTML file
    window = webview.create_window(
        title="BirhanEcho",
        url='UI/index.html',
        width=1000,
        height=700,
        resizable=True,
        min_size=(800, 600),
        fullscreen=True
    )

    window.events.loaded += initialize_cardinal

    webview.start(debug=False)


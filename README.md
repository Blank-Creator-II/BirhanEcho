# BirhanEcho

BirhanEcho is a voice-first desktop reader for educational books, designed to help visually impaired students read and study with greater independence. It turns structured textbook content into narrated pages, with spoken navigation, saved reading positions, and on-screen captions.

> **Project status:** This README describes the features present in the current code. PDF conversion uses Google's Gemini API yet not local AI, so BirhanEcho is not fully offline end to end. Already-converted `.audib` books can be read locally tho.

## Features

- **Voice-operated interface:** Use spoken commands to browse books and folders, open settings, navigate a book, and control playback. The app uses local Vosk speech recognition.
- **Textbook reading:** Read books page by page and block by block, with commands to move forward or backward, jump to a page, pause, resume, and replay.
- **Spoken term explanations:** A page can include pre-generated audio hyperlinks for key terms. Ask to “explain more” while reading a block that has one.
- **Resume where you stopped:** BirhanEcho saves the current book position and restores it when you return to that book.
- **Voice and speed options:** Choose an interface voice and adjust its speed through the spoken settings menu.
- **PDF-to-book workflow:** Select a PDF through the voice-driven file browser. Gemini analyzes its pages into structured reading content and Piper generates the audio, which is packaged with the manifest in a custom `.audib` file.
- **`.audib` book support:** Open an existing package from the library or the file browser. the custom package `.audib` contains a JSON reading manifest and its generated WAV audio.
- **Visual support:** A real-time audio visualizer and large high-contrast subtitles. Shout out to Sword Art Online: Alicization for the inspiration of the visualizer. 
- **Contextual help and repeated prompts:** Say “command help” for guidance appropriate to the current screen. Several menus and prompts repeat when idle.

## How it works

BirhanEcho has two main workflows:

1. **Read an existing `.audib` book.** Speech recognition, playback, and subtitles run locally after the book and its required voice assets are available.
2. **Convert a PDF.** The app extracts pages, sends them to Gemini for structured analysis, generates narration locally with Piper, and saves an `.audib` package. This workflow requires internet access and a Gemini API key currently. The prompt asks Gemini to preserve reading order, describe visual material, render equations in speech-friendly language, and identify terms for audio explanations; the results depend on the source PDF and model output. In the future this process is supposed to be replaced by a local custom AI or a different offline engine. 

## Getting started

### Requirements

- Python 3.11 with support for the pinned packages in [`requirements.txt`](requirements.txt)
- A working microphone and audio output device (speaker)
- A local Vosk speech-recognition model at `Vosk/model`
- A Piper voice model and matching JSON configuration. By default, the app expects `Voices/Grace/Grace.onnx` and its paired `.onnx.json` configuration which is currently hfc_female model of piper TTS adjusted for the app and renamed Grace.
- A Gemini API key if you want to convert PDFs
- A system webview supported by pywebview

Model files and user book data are excluded from version control. You need to provide the Vosk and Piper model assets locally before starting the application.

### Install and run

Run these commands from the repository root:

```bash
python -m venv .venv
```

Activate the virtual environment, then install the dependencies:

```bash
# Linux or macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
```

For PDF conversion, create a `.env` file in the repository root and add your API key:

```dotenv
GEMINI_API_KEY=your_api_key
```

Keep the key private; do not commit `.env`. Start BirhanEcho from the repository root:

```bash
python main.py
```

The voice-driven file browser for now starts in your `Documents` folder. Put PDFs or `.audib` files there (or in a subfolder) to browse and open them. Existing `.audib` files can also be placed in `Data/Books` to appear in the book library.

## Voice commands

The starter phrase is **“command”**. Begin commands with it; for example, say **“command help”** or **“command main menu.”** The available action depends on the current screen.

| What you want to do | Example spoken command |
| --- | --- |
| Get help or repeat speech | “command help”, “command repeat” |
| Return or open the main menu | “command go back”, “command main menu” |
| Browse books or add a book | “command list books”, “command upload” |
| Open settings or change speech | “command options”, “command change voice”, “command change speed” |
| Control playback | “command pause”, “command play”, “command stop” |
| Navigate while reading | “command go forward”, “command go backward”, “command move page” |
| Hear a term explanation, if available | “command explain more” |
| Resume or restart the current book | “command resume”, “command start over” |
| Exit | “command exit” |

When a prompt asks for a number, speak the requested page, book, or folder number without the starter phrase. In the file browser, choose a listed folder or file by its spoken number; say “command move back” to go up one folder.

## Current scope and limitations

- PDF analysis is **not offline**: conversion uses the Gemini API and may incur API usage costs.
- Reading an existing `.audib` package does not require Gemini or an internet connection.
- Diagram descriptions, equation narration, and term explanations are created during PDF analysis; their presence and accuracy depend on the generated content.
- Navigation is by reading block and page, not by sentence.
- Idle prompts repeat in selected menus and prompts; the repeat behavior is not a universal safety loop across every screen.
- The project is tested on low end devices up to a 4 GB RAM with Core i3 intel chip computer.

## Project layout

```text
main.py                    Desktop application entry point
cardinal_system.py         main controller/engine for the app (named after SAO's cardinal system) 
Player/                    Speech recognition, playback, TTS, and .audib files managers
Processor/                 PDF extraction, Gemini analysis, and progress storage
UI/                        Webview interface, visualizer, and subtitles
Data/                      Settings and application audio assets
master_prompt.md           Instructions used for Gemini analysis (not used directly just there for reference)
requirements.txt           Pinned Python dependencies
```

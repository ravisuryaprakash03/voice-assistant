# Python Voice Assistant

A personal assistant written in Python that listens to your voice commands, answers out loud, and automates small tasks like opening websites, searching the web and saving notes.

## Features

- Voice input using **SpeechRecognition** and voice output using **pyttsx3**
- Tells the time and date
- Opens websites (YouTube, Google, Gmail, GitHub, Stack Overflow, ...) and apps (Notepad, Calculator)
- Searches Google and YouTube ("search python tutorials", "play lofi music")
- Looks up topics on Wikipedia (no extra library needed)
- Takes and reads notes, saved in `notes.txt`
- Tells jokes and does simple small talk
- Works on Windows, macOS and Linux
- **Text mode** (`--text`) and automatic fallback to typing if no microphone is found

## Tech Used

- Python 3.8+
- Libraries: `SpeechRecognition`, `pyttsx3`, `sounddevice` for microphone access (plus built-in `datetime`, `webbrowser`, `subprocess`, `urllib`, `json`, `re`, `os`, `platform`)

## Project Structure

```
voiceassistant/
├── voice_assistant.py   # The assistant
├── requirements.txt     # SpeechRecognition, pyttsx3, sounddevice
├── README.md            # Documentation
└── notes.txt            # Created automatically when you save a note
```

## Installation

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
pip install -r requirements.txt
```

This installs `SpeechRecognition` (speech to text), `pyttsx3` (text to speech) and `sounddevice` (microphone access).

**About PyAudio:** many guides tell you to install `PyAudio`, but it has no ready-made installer for the newest Python versions (such as 3.14 on Windows), so `pip install pyaudio` fails with a "portaudio.h not found" error. This project therefore uses `sounddevice`, which installs everywhere. If PyAudio is already installed on your system, the assistant uses it automatically instead.

## Run

```bash
python voice_assistant.py           # voice mode
python voice_assistant.py --text    # type commands instead of speaking
```

An internet connection is needed for speech recognition (it uses Google's free web speech service) and for Wikipedia.

## Example Commands

| Say | What happens |
|---|---|
| "What time is it" | Speaks the current time |
| "What is the date today" | Speaks today's date |
| "Open YouTube" / "Open GitHub" | Opens the website |
| "Open calculator" / "Open notepad" | Opens the app |
| "Search python tutorials" | Google search |
| "Play lofi music" | YouTube search |
| "Wikipedia Albert Einstein" / "Who is Nikola Tesla" | Speaks a short summary |
| "Note buy milk" | Saves a note to `notes.txt` |
| "Read my notes" | Reads your latest notes |
| "Tell me a joke" | Tells a joke |
| "Help" | Lists what it can do |
| "Goodbye" | Quits |

## How It Works

1. `listen()` records audio from the microphone (waiting for you to start talking and stopping when you pause) and sends it to `recognizer.recognize_google()`, which returns the text.
2. `handle_command(text)` checks the text for keywords and decides what to do. It returns the reply and whether to keep running.
3. `speak(reply)` prints the reply and says it using `pyttsx3`.
4. A `while` loop repeats this until you say "goodbye".

Voice input/output are kept separate from the command logic, which makes the logic easy to test and lets the assistant fall back to typing.

## Adding Your Own Website or Command

Add a website in the `WEBSITES` dictionary:

```python
"netflix": "https://www.netflix.com",
```

Add a new command inside `handle_command()`:

```python
if "weather" in words:
    return "I can't check the weather yet.", True
```

## Troubleshooting

- **"No microphone library found"**: run `pip install sounddevice`. The assistant switches to text mode in the meantime.
- **"sounddevice could not open a microphone"**: on Windows open Settings > Privacy & security > Microphone and turn on "Let desktop apps access your microphone". Also check that a microphone is plugged in and set as the default input device.
- **It never hears me / hears too much noise**: change `MIN_SPEECH_LEVEL` near the top of `voice_assistant.py` (lower = more sensitive, higher = ignores background noise).
- **It doesn't understand me**: speak clearly, reduce background noise, and check your internet.
- **No voice output**: on Linux install `espeak`. On Windows and macOS the built-in voices are used.
- **A different voice**: change `VOICE_INDEX` at the top of the file.

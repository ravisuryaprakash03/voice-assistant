# ============================================================
# Voice Assistant
# Libraries: speech_recognition (hear you) + pyttsx3 (speak back)
# Also uses built-in modules: datetime, webbrowser, os, platform ...
#
# Run:   python voice_assistant.py          (voice mode)
#        python voice_assistant.py --text   (type instead of talking)
# ============================================================

import json
import os
import platform
import random
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import webbrowser
from array import array
from collections import deque
from datetime import datetime

# The two required libraries. If one is missing we explain how to
# install it instead of crashing with a confusing error.
try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

# Optional microphone backend. PyAudio is the usual choice, but it has no
# installer for brand-new Python versions (e.g. 3.14). sounddevice works on
# every Python version, so we use it when PyAudio is missing.
try:
    import sounddevice as sd
except Exception:       # ImportError, or OSError if the audio library is missing
    sd = None


ASSISTANT_NAME = "Jarvis"
VOICE_INDEX = 0          # 0 = first voice on your PC. Try 1 for a different voice.
SPEECH_RATE = 170        # words per minute
NOTES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes.txt")

# Websites the assistant can open. Add your own here!
WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "wikipedia": "https://www.wikipedia.org",
    "spotify": "https://open.spotify.com",
    "whatsapp": "https://web.whatsapp.com",
    "linkedin": "https://www.linkedin.com",
}

# Desktop apps, with the command for each operating system.
APPS = {
    "notepad": {"Windows": ["notepad.exe"],
                "Darwin": ["open", "-a", "TextEdit"],
                "Linux": ["gedit"]},
    "calculator": {"Windows": ["calc.exe"],
                   "Darwin": ["open", "-a", "Calculator"],
                   "Linux": ["gnome-calculator"]},
}

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "Why did the Python programmer need glasses? Because he couldn't C!",
    "There are 10 types of people: those who understand binary and those who don't.",
    "I would tell you a UDP joke, but you might not get it.",
]


# ------------------------------------------------------------
# VOICE OUTPUT (text-to-speech with pyttsx3)
# ------------------------------------------------------------

engine = None   # the speech engine, created by setup_speech()


def setup_speech():
    """Start the text-to-speech engine. Returns True if it works."""
    global engine
    if pyttsx3 is None:
        print("[!] pyttsx3 is not installed. Run: pip install pyttsx3")
        return False
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        # Safe voice choice: only use VOICE_INDEX if that voice exists
        if voices and VOICE_INDEX < len(voices):
            engine.setProperty("voice", voices[VOICE_INDEX].id)
        engine.setProperty("rate", SPEECH_RATE)
        return True
    except Exception as error:
        print(f"[!] Could not start text-to-speech ({error}). I'll only print replies.")
        engine = None
        return False


def speak(text):
    """Print the reply and say it out loud (if speech is available)."""
    print(f"{ASSISTANT_NAME}: {text}")
    if engine is not None:
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass   # never crash just because speaking failed


# ------------------------------------------------------------
# VOICE INPUT (speech recognition)
# ------------------------------------------------------------

recognizer = None       # created by setup_microphone()
mic_backend = None      # "pyaudio" or "sounddevice"

SAMPLE_RATE = 16000     # samples per second (good for speech)
CHUNK_SECONDS = 0.2     # we check the volume every 0.2 seconds
MIN_SPEECH_LEVEL = 350  # lowest volume we treat as speech. Raise it in a noisy
                        # room, lower it if the assistant doesn't hear you.


def setup_microphone():
    """Check that a microphone works. Returns True if we can listen."""
    global recognizer, mic_backend
    if sr is None:
        print("[!] speech_recognition is not installed. Run: pip install SpeechRecognition")
        return False
    recognizer = sr.Recognizer()

    # Option 1: PyAudio (used by SpeechRecognition's own Microphone class)
    try:
        if sr.Microphone.list_microphone_names():
            mic_backend = "pyaudio"
            return True
    except Exception:
        pass   # PyAudio isn't installed. Try the next option.

    # Option 2: sounddevice
    if sd is not None:
        try:
            sd.check_input_settings(samplerate=SAMPLE_RATE, channels=1, dtype="int16")
            mic_backend = "sounddevice"
            return True
        except Exception as error:
            print(f"[!] sounddevice could not open a microphone ({error}).")
            print("    Check that a microphone is connected and allowed in Windows")
            print("    Settings > Privacy > Microphone.")
            return False

    print("[!] No microphone library found. Run: pip install sounddevice")
    return False


def rms(chunk):
    """Volume of a chunk of 16-bit audio (bigger number = louder)."""
    samples = array("h")
    samples.frombytes(chunk)
    if len(samples) == 0:
        return 0.0
    return (sum(x * x for x in samples) / len(samples)) ** 0.5


def record_sounddevice(read_chunk=None, wait_limit=6.0, phrase_limit=10.0,
                       silence_after=1.0):
    """Record one spoken phrase with sounddevice.
    - Waits up to wait_limit seconds for you to start talking.
    - Stops after silence_after seconds of quiet, or phrase_limit seconds.
    Returns the raw audio bytes, or None if nobody spoke.
    (read_chunk is only used for testing without a real microphone.)
    """
    frames_per_chunk = int(SAMPLE_RATE * CHUNK_SECONDS)
    stream = None
    if read_chunk is None:
        stream = sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1,
                                   dtype="int16", blocksize=frames_per_chunk)
        stream.start()

        def read_chunk():
            data, _overflowed = stream.read(frames_per_chunk)
            return bytes(data)

    try:
        # 1. Measure the background noise for 0.6 seconds
        noise = [rms(read_chunk()) for _ in range(3)]
        threshold = max(sum(noise) / len(noise) * 3, MIN_SPEECH_LEVEL)

        # 2. Wait for speech, then record until you stop talking
        before_speech = deque(maxlen=2)   # keep the moment just before you spoke
        recorded = []
        started = False
        waited = 0.0
        spoken = 0.0
        quiet_chunks = 0
        max_quiet_chunks = int(silence_after / CHUNK_SECONDS)

        while True:
            chunk = read_chunk()
            loud = rms(chunk) > threshold

            if not started:
                waited += CHUNK_SECONDS
                if loud:
                    started = True
                    recorded = list(before_speech) + [chunk]
                elif waited >= wait_limit:
                    return None                      # nobody spoke
                else:
                    before_speech.append(chunk)
            else:
                recorded.append(chunk)
                spoken += CHUNK_SECONDS
                quiet_chunks = 0 if loud else quiet_chunks + 1
                if quiet_chunks >= max_quiet_chunks or spoken >= phrase_limit:
                    break

        return b"".join(recorded)
    finally:
        if stream is not None:
            stream.stop()
            stream.close()


def capture_audio():
    """Record from the microphone. Returns audio, or None if nobody spoke."""
    if mic_backend == "sounddevice":
        data = record_sounddevice()
        if data is None:
            return None
        return sr.AudioData(data, SAMPLE_RATE, 2)    # 2 bytes per sample (16-bit)

    with sr.Microphone() as source:                  # PyAudio route
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            return recognizer.listen(source, timeout=6, phrase_time_limit=8)
        except sr.WaitTimeoutError:
            return None


def listen():
    """Listen through the microphone and return what was said as lowercase
    text. Returns '' if nothing was understood."""
    print("\nListening...")
    try:
        audio = capture_audio()
    except Exception as error:
        print(f"[!] Microphone problem: {error}")
        return ""
    if audio is None:
        return ""          # nobody spoke

    try:
        print("Recognizing...")
        text = recognizer.recognize_google(audio, language="en-IN")   # needs internet
        print(f"You said: {text}")
        return text.lower()
    except sr.UnknownValueError:
        speak("Sorry, I didn't catch that. Please say it again.")
    except sr.RequestError:
        speak("I can't reach the speech service. Please check your internet connection.")
    return ""


def get_typed_command():
    """Text mode: read a command from the keyboard instead."""
    try:
        return input("\nYou (type): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "exit"


# ------------------------------------------------------------
# ACTIONS (the "automation" part)
# ------------------------------------------------------------

def open_website(url):
    webbrowser.open(url)


def open_app(app_name):
    """Open a desktop app. Returns True if it started."""
    command = APPS[app_name].get(platform.system())
    if command is None:
        return False
    try:
        subprocess.Popen(command)
        return True
    except (FileNotFoundError, OSError):
        return False


def search_web(site, term):
    """Open a Google or YouTube search for the given words."""
    query = urllib.parse.quote_plus(term)          # "cute cats" -> "cute+cats"
    if site == "youtube":
        webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
    else:
        webbrowser.open(f"https://www.google.com/search?q={query}")


def wikipedia_summary(topic):
    """Get a short summary from Wikipedia (needs internet, no extra library)."""
    title = urllib.parse.quote(topic.strip().replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    request = urllib.request.Request(url, headers={"User-Agent": "VoiceAssistantProject/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        summary = data.get("extract", "")
        if not summary:
            return f"I couldn't find anything about {topic}."
        # Keep only the first two sentences so it's not too long to listen to
        sentences = re.split(r"(?<=[.!?])\s+", summary)
        return " ".join(sentences[:2])
    except Exception:
        return f"Sorry, I couldn't look up {topic}. Check your internet or try another topic."


def save_note(text):
    """Add a note, with the date and time, to notes.txt."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(NOTES_FILE, "a", encoding="utf-8") as file:
        file.write(f"[{stamp}] {text}\n")


def read_notes(count=3):
    """Return the last few notes as a single piece of text."""
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        return "You don't have any notes yet."
    if not lines:
        return "You don't have any notes yet."
    # Remove the "[date time]" part so it sounds natural when spoken
    last = [re.sub(r"^\[[^\]]*\]\s*", "", line) for line in lines[-count:]]
    return "Your latest notes are: " + ". ".join(last)


# ------------------------------------------------------------
# COMMAND HANDLER: decides what to do with what you said
# Returns (reply_text, keep_running)
# ------------------------------------------------------------

def text_after(command, *keywords):
    """Return the part of the command after the first keyword that is found.
    text_after("note buy milk", "note")  ->  "buy milk" """
    for keyword in keywords:
        if keyword in command:
            return command.split(keyword, 1)[1].strip()
    return ""


def handle_command(command):
    command = command.lower().strip()
    words = set(re.findall(r"[a-z']+", command))

    if command == "":
        return "", True

    # --- Notes (checked first so a note can contain words like "goodbye") ---
    if "notes" in words and ("read" in words or "show" in words or "my" in words):
        return read_notes(), True
    if command.startswith("note") or "take a note" in command or command.startswith("remember"):
        note = text_after(command, "take a note", "note", "remember")
        note = re.sub(r"^(that|down)\s+", "", note)
        if note == "":
            return "What would you like me to note? Say, note buy milk.", True
        save_note(note)
        return f"Okay, I saved your note: {note}", True

    # --- Exit ---
    if words & {"exit", "quit", "stop", "goodbye", "bye", "sleep"}:
        return "Goodbye! Have a great day.", False

    # --- Help ---
    if "help" in words or "what can you do" in command:
        return ("I can tell the time and date, open websites like YouTube and Google, "
                "open Notepad or the Calculator, search Google or YouTube, "
                "look things up on Wikipedia, take notes, and tell jokes. "
                "Say goodbye to stop."), True

    # --- Wikipedia ---
    asks_wikipedia = ("wikipedia" in words and "open" not in words)
    if asks_wikipedia or command.startswith(("who is", "tell me about")):
        topic = text_after(command, "wikipedia for", "wikipedia", "tell me about", "who is")
        if topic == "":
            topic = command.replace("wikipedia", "").replace("search", "").strip()
        topic = re.sub(r"^(for|about)\s+", "", topic)
        if topic == "":
            return "What should I look up on Wikipedia?", True
        return wikipedia_summary(topic), True

    # --- YouTube: "play X" or "search X on youtube" ---
    if "play" in words or ("youtube" in words and "search" in words):
        term = re.sub(r"\b(on|in)\s+youtube\b|\byoutube\b|\bsearch\b|\bplay\b|\bfor\b", "", command)
        term = term.strip()
        if term == "":
            return "What would you like me to play?", True
        search_web("youtube", term)
        return f"Searching YouTube for {term}.", True

    # --- Google search ---
    if "search" in words or command.startswith("google "):
        term = re.sub(r"\b(on|in)\s+google\b|\bgoogle\b|\bsearch\b|\bfor\b", "", command).strip()
        if term == "":
            return "What should I search for?", True
        search_web("google", term)
        return f"Searching Google for {term}.", True

    # --- Open websites and apps ---
    if "open" in words or "launch" in words:
        for app_name in APPS:
            if app_name in command:
                if open_app(app_name):
                    return f"Opening {app_name}.", True
                return f"Sorry, I couldn't open {app_name} on this computer.", True
        for site_name, url in WEBSITES.items():
            if site_name in command:
                open_website(url)
                return f"Opening {site_name}.", True
        return "Which website or app should I open?", True

    # --- Time and date ---
    if "time" in words:
        return "The time is " + datetime.now().strftime("%I:%M %p") + ".", True
    if "date" in words or "what day" in command or "what is today" in command:
        return "Today is " + datetime.now().strftime("%A, %d %B %Y") + ".", True

    # --- Small talk ---
    if "joke" in words or "laugh" in words or "funny" in words:
        return random.choice(JOKES), True
    if words & {"hello", "hi", "hey"}:
        return "Hello! How can I help you?", True
    if "how are you" in command:
        return "I'm doing great, thank you for asking!", True
    if "your name" in command or "who are you" in command:
        return f"I'm {ASSISTANT_NAME}, your Python voice assistant.", True
    if words & {"thanks", "thank"}:
        return "You're welcome!", True

    return "Sorry, I don't know that command yet. Say help to hear what I can do.", True


# ------------------------------------------------------------
# MAIN PROGRAM
# ------------------------------------------------------------

def main():
    force_text = "--text" in sys.argv

    setup_speech()
    voice_mode = (not force_text) and setup_microphone()

    print("=" * 52)
    print(f"  {ASSISTANT_NAME} - Python Voice Assistant")
    print("  Mode:", f"VOICE via {mic_backend} (speak your commands)" if voice_mode
          else "TEXT (type your commands)")
    print("  Say 'help' for ideas, 'goodbye' to quit.")
    print("=" * 52)

    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 18:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    speak(f"{greeting}! I am {ASSISTANT_NAME}. How can I help you?")

    while True:
        command = listen() if voice_mode else get_typed_command()
        reply, keep_running = handle_command(command)
        if reply:
            speak(reply)
        if not keep_running:
            break


if __name__ == "__main__":
    main()
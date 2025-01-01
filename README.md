# VoiceTranscribe - Audio Transcription from Videos

This program is a desktop application that allows transcribing audio from videos (mainly from YouTube) to text. Here is the breakdown of its main components:

## Key Features:

- Graphical interface using PyQt5
- Audio download from videos using yt-dlp
- Audio transcription using OpenAI's Whisper model
- Error handling and timeouts
- Progress bar and visual feedback

## Main Functions:

- **download_audio(url):**
  - Downloads the video's audio
  - Converts the file to MP3
  - Checks size and format
- **transcribe_audio(audio_file):**
  - Uses the Whisper model to convert audio to text
  - Handles timeouts and errors
- **save_transcription(text, file_name):**
  - Saves the transcribed text to a file

### Security Features:

- URL validation
- File size limit
- Timeout for lengthy operations
- Filename sanitization
- Error handling

### Multithreading:

- Uses QThread to:
  - Prevent the interface from freezing during transcription
  - Allow cancellation of the operation
  - Display real-time progress

## This Program is Useful for:

- Transcribing video lectures or classes
- Obtaining subtitles from videos
- Converting audio content to text for analysis or archiving

## System Requirements:

- Python 3.8 or higher
- Sufficient disk space for temporary files
- Internet connection

## Dependencies (pip install):

- yt-dlp
- whisper
- PyQt5
- PyQtWebEngine
- PySide6

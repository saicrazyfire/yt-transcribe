# YouTube Transcribe

A simple Python script to download YouTube video audio and transcribe it using local Whisper models. Automatically uses YouTube's built-in transcripts when available.

## Requirements

- Python 3.10+
- `yt-dlp` CLI tool (must be installed separately)
- `uv` package manager (optional, for dependency management)

## Installation

### Using uv (recommended)

You can run the script without installing dependencies globally:

```bash
uv run --with openai-whisper transcribe.py <youtube_url>
```

Or install dependencies first:

```bash
uv sync
uv run transcribe.py <youtube_url>
```

### Using pip

```bash
pip install openai-whisper
python transcribe.py <youtube_url>
```

## Usage

```bash
python transcribe.py <youtube_url> [-o OUTPUT_PREFIX] [-f FORMAT ...] [--txt]
```

### Arguments

- `youtube_url`: The YouTube video URL to transcribe
- `-o, --output`: Output file prefix (without extension). Default: uses video title and ID (e.g., `Video_Title_WqIg_Ybbehc`)
- `-f, --format`: Output format(s) to generate. Can be specified multiple times. Options: `txt`, `srt`, `json`, `all`. Default: only `vtt` is saved.
- `--txt`: Enable plain text (.txt) output without timestamps (for post-processing). Equivalent to `-f txt`.

### Examples

```bash
# Basic usage (saves only .vtt file to output/ folder)
python transcribe.py https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Custom output filename
python transcribe.py https://www.youtube.com/watch?v=dQw4w9WgXcQ -o my_video

# Save plain text format (no timestamps, for post-processing)
python transcribe.py https://www.youtube.com/watch?v=dQw4w9WgXcQ --txt

# Save additional formats
python transcribe.py https://www.youtube.com/watch?v=dQw4w9WgXcQ -f txt -f srt

# Save all formats
python transcribe.py https://www.youtube.com/watch?v=dQw4w9WgXcQ -f all

# Using uv without installing dependencies
uv run --with openai-whisper transcribe.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

## Output Formats

Transcripts are saved to the `output/` subfolder. By default, only the `.vtt` format is generated. Use the `-f` flag or `--txt` flag to specify additional formats:

- `.vtt` - WebVTT format with timestamps (always generated)
- `.txt` - Plain text transcript **without timestamps** (for post-processing). Use `--txt` flag or `-f txt`.
- `.srt` - SRT subtitle format with timestamps
- `.json` - Structured JSON with timestamps

**Note**: The `.txt` format intentionally excludes timestamps since `.vtt` and `.srt` already provide timestamped versions. This makes `.txt` ideal for text processing, analysis, or feeding into other tools.

All files use the same base name. By default, the filename includes the video title and video ID (e.g., `Video_Title_WqIg_Ybbehc.vtt`). You can override this with the `-o` option.

## How It Works

1. **Check for YouTube transcripts**: First attempts to download YouTube's built-in transcripts (manual or auto-generated)
2. **Fallback to audio transcription**: If no transcripts are available, downloads audio and transcribes using Whisper
3. **Format conversion**: Converts the transcript to multiple output formats

## Whisper Models

**No manual download needed!** Whisper models are automatically downloaded on first use. The script uses the "base" model by default, which provides a good balance of speed and accuracy. Models are cached in `~/.cache/whisper/` after the first download.

Available models (from smallest/fastest to largest/most accurate):
- `tiny` - Fastest, least accurate
- `base` - Good balance (default)
- `small` - Better accuracy
- `medium` - High accuracy
- `large` - Best accuracy, slowest

You can modify the model in `transcribe.py` by changing `whisper.load_model("base")` to your preferred model.

## WhisperX vs OpenAI Whisper

**WhisperX** is an enhanced version that provides:
- **Word-level timestamps** (vs segment-level in standard Whisper)
- Better handling of long audio files (reduces drift and repetition)
- More accurate timestamps using forced phoneme alignment
- Voice Activity Detection (VAD) for better segmentation

**When to use WhisperX:**
- You need precise word-level timestamps for subtitles
- Working with very long videos (>30 minutes)
- Need high-precision subtitle synchronization

**When standard Whisper is fine:**
- Simple transcript extraction
- Short to medium videos
- You don't need word-level precision

The current script uses OpenAI Whisper for simplicity. If you need WhisperX features, you can install it separately (`pip install whisperx`) and modify the transcription function.

## Notes

- Temporary files are automatically cleaned up
- Requires `yt-dlp` to be installed and available in your PATH
- First transcription will be slower as it downloads the model (~150MB for "base" model)
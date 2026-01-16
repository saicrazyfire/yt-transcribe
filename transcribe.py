#!/usr/bin/env python3
"""
YouTube Video Transcription Script

Downloads audio from YouTube videos and transcribes them using local Whisper model.
Falls back to YouTube's built-in transcripts if available.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple


def run_command(cmd: list[str], check: bool = True) -> Tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, and stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr


def get_video_info(url: str) -> Tuple[str, str]:
    """Get video title and ID from YouTube URL."""
    cmd = [
        "yt-dlp",
        "--get-title",
        "--get-id",
        url
    ]
    
    exit_code, stdout, stderr = run_command(cmd, check=False)
    
    if exit_code == 0 and stdout.strip():
        lines = stdout.strip().split('\n')
        if len(lines) >= 2:
            title = lines[0].strip()
            video_id = lines[1].strip()
        elif len(lines) == 1:
            # Sometimes title and ID are on same line or only one is returned
            # Try to extract ID from URL
            video_id_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
            video_id = video_id_match.group(1) if video_id_match else "unknown"
            title = lines[0].strip()
        else:
            title = "unknown"
            video_id = "unknown"
    else:
        # Fallback: extract ID from URL
        video_id_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
        video_id = video_id_match.group(1) if video_id_match else "unknown"
        title = "unknown"
    
    # Sanitize title for filename
    title = re.sub(r'[<>:"/\\|?*]', '_', title)
    title = title[:100]  # Limit length
    
    return title, video_id


def check_youtube_transcript(url: str, temp_dir: Path) -> Optional[Path]:
    """Check if YouTube has built-in transcripts available."""
    print("Checking for YouTube transcripts...")
    vtt_file = temp_dir / "transcript.vtt"
    
    cmd = [
        "yt-dlp",
        "--write-subs",
        "--sub-format", "vtt",
        "--skip-download",
        "--sub-lang", "en",
        "-o", str(temp_dir / "transcript"),
        url
    ]
    
    exit_code, stdout, stderr = run_command(cmd, check=False)
    
    if exit_code == 0:
        # Find the actual VTT file that was created
        vtt_files = list(temp_dir.glob("*.vtt"))
        if vtt_files:
            vtt_path = vtt_files[0]
            # Check if file has actual content (more than just WEBVTT header)
            with open(vtt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                # Check if there's actual transcript content (not just WEBVTT header)
                if len(content) > 10 and re.search(r'\d{2}:\d{2}:\d{2}', content):
                    print(f"Found YouTube transcript: {vtt_path}")
                    return vtt_path
    
    # Try without language restriction
    cmd = [
        "yt-dlp",
        "--write-auto-subs",
        "--sub-format", "vtt",
        "--skip-download",
        "-o", str(temp_dir / "transcript"),
        url
    ]
    
    exit_code, stdout, stderr = run_command(cmd, check=False)
    
    if exit_code == 0:
        vtt_files = list(temp_dir.glob("*.vtt"))
        if vtt_files:
            vtt_path = vtt_files[0]
            # Check if file has actual content
            with open(vtt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if len(content) > 10 and re.search(r'\d{2}:\d{2}:\d{2}', content):
                    print(f"Found YouTube auto-generated transcript: {vtt_path}")
                    return vtt_path
    
    print("No YouTube transcripts found, will download audio for transcription")
    return None


def parse_vtt(vtt_file: Path) -> list[dict]:
    """Parse VTT file and extract text with timestamps."""
    segments = []
    with open(vtt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # VTT format: timestamp lines followed by text
    pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\n(.*?)(?=\n\n|\n\d{2}:|$)'
    matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
    
    for match in matches:
        start_time = match.group(1)
        end_time = match.group(2)
        text = match.group(3).strip()
        # Remove VTT formatting tags
        text = re.sub(r'<[^>]+>', '', text)
        if text:
            segments.append({
                'start': start_time,
                'end': end_time,
                'text': text
            })
    
    return segments


def time_to_seconds(time_str: str) -> float:
    """Convert VTT time format (HH:MM:SS.mmm) to seconds."""
    parts = time_str.split(':')
    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def save_txt(segments: list[dict], output_file: Path):
    """Save transcript as plain text."""
    with open(output_file, 'w', encoding='utf-8') as f:
        for seg in segments:
            f.write(seg['text'] + '\n')


def save_vtt(segments: list[dict], output_file: Path):
    """Save transcript as WebVTT format."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("WEBVTT\n\n")
        for seg in segments:
            f.write(f"{seg['start']} --> {seg['end']}\n")
            f.write(f"{seg['text']}\n\n")


def save_srt(segments: list[dict], output_file: Path):
    """Save transcript as SRT format."""
    with open(output_file, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start_sec = time_to_seconds(seg['start'])
            end_sec = time_to_seconds(seg['end'])
            f.write(f"{i}\n")
            f.write(f"{seconds_to_srt_time(start_sec)} --> {seconds_to_srt_time(end_sec)}\n")
            f.write(f"{seg['text']}\n\n")


def save_json(segments: list[dict], output_file: Path):
    """Save transcript as JSON format."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)


def download_audio(url: str, temp_dir: Path) -> Path:
    """Download audio from YouTube video."""
    print("Downloading audio...")
    audio_file = temp_dir / "audio.wav"
    
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "wav",
        "-o", str(audio_file),
        url
    ]
    
    exit_code, stdout, stderr = run_command(cmd)
    if exit_code != 0:
        print(f"Error downloading audio: {stderr}", file=sys.stderr)
        sys.exit(1)
    
    # yt-dlp might add extension, find the actual file
    audio_files = list(temp_dir.glob("*.wav"))
    if audio_files:
        return audio_files[0]
    
    return audio_file


def transcribe_audio(audio_file: Path) -> list[dict]:
    """Transcribe audio using Whisper."""
    print("Transcribing audio with Whisper...")
    
    try:
        import whisper
    except ImportError:
        print("Error: openai-whisper not installed. Install with: pip install openai-whisper", file=sys.stderr)
        sys.exit(1)
    
    model = whisper.load_model("base")
    result = model.transcribe(str(audio_file))
    
    segments = []
    for seg in result["segments"]:
        segments.append({
            'start': seconds_to_vtt_time(seg['start']),
            'end': seconds_to_vtt_time(seg['end']),
            'text': seg['text'].strip()
        })
    
    return segments


def seconds_to_vtt_time(seconds: float) -> str:
    """Convert seconds to VTT time format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def main():
    parser = argparse.ArgumentParser(
        description="Download and transcribe YouTube videos"
    )
    parser.add_argument(
        "url",
        help="YouTube video URL"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file prefix (without extension)",
        default="transcript"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["txt", "srt", "json", "all"],
        action="append",
        help="Output format(s) to generate (can be specified multiple times). Default: vtt only. Use 'all' for all formats."
    )
    parser.add_argument(
        "--txt",
        action="store_true",
        help="Enable plain text (.txt) output without timestamps (for post-processing). Equivalent to -f txt."
    )
    
    args = parser.parse_args()
    
    # Get video info for filename
    print("Getting video information...")
    video_title, video_id = get_video_info(args.url)
    print(f"Video: {video_title} ({video_id})")
    
    # Determine which formats to save
    formats_to_save = set()
    if args.format:
        if "all" in args.format:
            formats_to_save = {"vtt", "txt", "srt", "json"}
        else:
            formats_to_save = set(args.format)
            formats_to_save.add("vtt")  # Always include vtt
    else:
        formats_to_save = {"vtt"}  # Default: only vtt
    
    # Add txt if --txt flag is used
    if args.txt:
        formats_to_save.add("txt")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Check for YouTube transcripts first
        vtt_file = check_youtube_transcript(args.url, temp_path)
        
        if vtt_file:
            segments = parse_vtt(vtt_file)
            if len(segments) == 0:
                print("YouTube transcript is empty, falling back to audio transcription...")
                # Download audio and transcribe
                audio_file = download_audio(args.url, temp_path)
                segments = transcribe_audio(audio_file)
                print(f"Transcribed {len(segments)} segments")
            else:
                print(f"Extracted {len(segments)} segments from YouTube transcript")
        else:
            # Download audio and transcribe
            audio_file = download_audio(args.url, temp_path)
            segments = transcribe_audio(audio_file)
            print(f"Transcribed {len(segments)} segments")
        
        # Create output directory
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # Generate output filename with video title and ID
        if args.output == "transcript":
            # Use video title and ID for default filename
            output_filename = f"{video_title}_{video_id}"
        else:
            output_filename = args.output
        
        # Save in requested formats
        output_base = output_dir / output_filename
        print(f"\nSaving transcripts to {output_dir}/")
        
        if "vtt" in formats_to_save:
            save_vtt(segments, output_base.with_suffix('.vtt'))
            print(f"  Saved: {output_base.with_suffix('.vtt')}")
        
        if "txt" in formats_to_save:
            save_txt(segments, output_base.with_suffix('.txt'))
            print(f"  Saved: {output_base.with_suffix('.txt')}")
        
        if "srt" in formats_to_save:
            save_srt(segments, output_base.with_suffix('.srt'))
            print(f"  Saved: {output_base.with_suffix('.srt')}")
        
        if "json" in formats_to_save:
            save_json(segments, output_base.with_suffix('.json'))
            print(f"  Saved: {output_base.with_suffix('.json')}")
        
        print("Done!")


if __name__ == "__main__":
    main()

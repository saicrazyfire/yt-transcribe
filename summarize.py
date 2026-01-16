#!/usr/bin/env python3
"""
YouTube Transcript Summarization Script

Summarizes transcript files using OpenAI-compatible API (supports local models).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed. Install with: pip install openai", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("Error: python-dotenv package not installed. Install with: pip install python-dotenv", file=sys.stderr)
    sys.exit(1)


def load_system_prompt(prompt_file: Path) -> str:
    """Load system prompt from file."""
    if not prompt_file.exists():
        print(f"Error: System prompt file not found: {prompt_file}", file=sys.stderr)
        sys.exit(1)
    
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read().strip()


def parse_transcript_file(file_path: Path) -> str:
    """Parse transcript file and extract text content."""
    content = file_path.read_text(encoding='utf-8')
    
    # Handle different formats
    if file_path.suffix == '.txt':
        # Plain text - return as is
        return content.strip()
    
    elif file_path.suffix == '.vtt':
        # WebVTT format - extract text
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            # Skip WEBVTT header, timestamps, and empty lines
            if (line and 
                not line.startswith('WEBVTT') and 
                not re.match(r'^\d{2}:\d{2}:\d{2}', line) and
                not '-->' in line and
                not line.isdigit()):
                # Remove VTT formatting tags
                line = re.sub(r'<[^>]+>', '', line)
                if line:
                    lines.append(line)
        return '\n'.join(lines)
    
    elif file_path.suffix == '.srt':
        # SRT format - extract text
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            # Skip timestamps and sequence numbers
            if (line and 
                not re.match(r'^\d+$', line) and
                not re.match(r'^\d{2}:\d{2}:\d{2}', line) and
                not '-->' in line):
                if line:
                    lines.append(line)
        return '\n'.join(lines)
    
    elif file_path.suffix == '.json':
        # JSON format - extract text from segments
        try:
            data = json.loads(content)
            if isinstance(data, list):
                # List of segments
                texts = [seg.get('text', '') for seg in data if isinstance(seg, dict)]
                return '\n'.join(texts)
            else:
                return str(data)
        except json.JSONDecodeError:
            return content
    
    else:
        # Unknown format - try to return as text
        return content.strip()


def list_transcript_files(output_dir: Path) -> list[Path]:
    """List all transcript files in output directory."""
    transcript_extensions = ['.txt', '.vtt', '.srt', '.json']
    files = []
    
    for ext in transcript_extensions:
        files.extend(output_dir.glob(f'*{ext}'))
    
    # Remove duplicates (same base name, different extensions)
    seen = set()
    unique_files = []
    for f in sorted(files):
        base = f.stem
        if base not in seen:
            seen.add(base)
            unique_files.append(f)
    
    return unique_files


def select_transcript_file(output_dir: Path) -> Optional[Path]:
    """Interactive selection of transcript file."""
    files = list_transcript_files(output_dir)
    
    if not files:
        print(f"No transcript files found in {output_dir}")
        return None
    
    print("\nAvailable transcript files:")
    for i, file_path in enumerate(files, 1):
        print(f"  {i}. {file_path.name}")
    
    while True:
        try:
            choice = input(f"\nSelect a file (1-{len(files)}) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                return None
            
            index = int(choice) - 1
            if 0 <= index < len(files):
                return files[index]
            else:
                print(f"Please enter a number between 1 and {len(files)}")
        except ValueError:
            print("Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return None


def summarize_transcript(
    transcript_text: str,
    system_prompt: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: str = "gpt-3.5-turbo",
    max_tokens: Optional[int] = None
) -> str:
    """Summarize transcript using OpenAI API."""
    client = OpenAI(
        api_key=api_key or "not-needed",  # Not needed for local models
        base_url=base_url
    )
    
    print(f"Summarizing using model: {model}")
    if base_url:
        print(f"Using base URL: {base_url}")
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Please summarize the following transcript:\n\n{transcript_text}"}
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"Error calling API: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Summarize YouTube transcript files using OpenAI-compatible API"
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to transcript file (optional - will prompt if not provided)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory containing transcript files (default: output)"
    )
    parser.add_argument(
        "--system-prompt",
        type=Path,
        default=Path("system_prompt.txt"),
        help="Path to system prompt file (default: system_prompt.txt)"
    )
    parser.add_argument(
        "--base-url",
        help="Base URL for OpenAI API (for local models, e.g., http://localhost:1234/v1)"
    )
    parser.add_argument(
        "--api-key",
        help="API key for OpenAI API (default: not needed for local models)"
    )
    parser.add_argument(
        "--model",
        default="gpt-3.5-turbo",
        help="Model name to use (default: gpt-3.5-turbo)"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        help="Maximum tokens in response (optional)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file for summary (default: print to stdout)"
    )
    
    args = parser.parse_args()
    
    # Load environment variables from .env file
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
        print("Loaded environment variables from .env file")
    
    # Get API key and base URL from environment or arguments
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    base_url = args.base_url or os.getenv("OPENAI_BASE_URL")
    
    # Determine which file to process
    if args.file:
        transcript_file = Path(args.file)
        if not transcript_file.exists():
            print(f"Error: File not found: {transcript_file}", file=sys.stderr)
            sys.exit(1)
    else:
        # Interactive selection
        transcript_file = select_transcript_file(args.output_dir)
        if not transcript_file:
            print("No file selected.")
            sys.exit(0)
    
    print(f"\nProcessing: {transcript_file.name}")
    
    # Load system prompt
    system_prompt = load_system_prompt(args.system_prompt)
    
    # Parse transcript
    print("Reading transcript...")
    transcript_text = parse_transcript_file(transcript_file)
    
    if not transcript_text:
        print("Error: Transcript file appears to be empty", file=sys.stderr)
        sys.exit(1)
    
    print(f"Transcript length: {len(transcript_text)} characters")
    
    # Summarize
    summary = summarize_transcript(
        transcript_text=transcript_text,
        system_prompt=system_prompt,
        base_url=base_url,
        api_key=api_key,
        model=args.model,
        max_tokens=args.max_tokens
    )
    
    # Output summary
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(summary, encoding='utf-8')
        print(f"\nSummary saved to: {output_path}")
    else:
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(summary)
        print("="*80)


if __name__ == "__main__":
    main()

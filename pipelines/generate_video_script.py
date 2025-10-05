#!/usr/bin/env python3
"""
CLI tool to generate video scripts from daily reports.
Run this after daily_run.py has completed.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load environment variables from .env.local
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / '.env.local')

from pipelines.video_script_generator import VideoScriptGenerator


def main():
    # Setup Gemini
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set in environment")
        sys.exit(1)

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    # Load today's report
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    report_path = Path(__file__).parents[1] / "outputs" / "daily" / f"{timestamp}.json"

    if not report_path.exists():
        print(f"ERROR: No report found for {timestamp}")
        print(f"Expected location: {report_path}")
        print("\nMake sure to run daily_run.py first to generate the daily report.")
        sys.exit(1)

    print(f"Loading report from: {report_path}")
    with open(report_path, 'r', encoding='utf-8') as f:
        report_data = json.load(f)

    # Generate script
    print("\nGenerating video script...")
    generator = VideoScriptGenerator(model)
    result = generator.generate_daily_script(report_data)

    if "error" in result:
        print(f"\nERROR: {result['error']}")
        print("\nTip: Make sure your daily report contains items with quality_score >= 6")
        sys.exit(1)

    if not result.get("success"):
        print("\nERROR: Script generation failed")
        sys.exit(1)

    # Print success info
    print("\n" + "=" * 60)
    print("✓ SUCCESS: Video script generated!")
    print("=" * 60)
    print(f"\nScript file: {result['script_path']}")
    print(f"Storyboard:  {result['storyboard_path']}")
    print(f"\nSources used: {result['metadata']['num_sources']}")
    print(f"Avg quality:  {result['metadata']['avg_quality_score']:.1f}/10")
    print("\nTop 3 sources:")
    for idx, source in enumerate(result['sources'][:3], 1):
        score = source.get('quality_score', 'N/A')
        print(f"  {idx}. [{score}/10] {source.get('title', 'Unknown')[:60]}...")

    print("\n" + "=" * 60)
    print("PREVIEW:")
    print("=" * 60)
    print(result['script'])


if __name__ == "__main__":
    main()

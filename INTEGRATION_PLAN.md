# Integration Plan: Scheduler + YouTubeAgency

## 🎯 Goal
Leverage existing YouTubeAgency transcript tools to enhance the scheduler with:
1. Full video transcript fetching
2. Deep content analysis
3. Quality scoring based on content
4. Automated video script generation

---

## 📊 EXISTING INFRASTRUCTURE ANALYSIS

### ✅ What You Already Have

#### 1. **YouTubeAgency Tools** (`/YouTubeAgency/youtube_analysis_agent/tools/`)

**A. `FetchVideoTranscript` (fetch_video_transcript.py)**
- ✅ Extracts video ID from URLs
- ✅ Fetches full transcripts with timestamps
- ✅ Multiple fallback methods:
  1. MCP server (http://localhost:3000)
  2. YouTube Transcript API
  3. Graceful error handling
- ✅ Saves transcript + metadata to output files
- ✅ Caching to avoid redundant API calls
- ✅ Rate limiting (5 videos per channel max)

**B. `getTranscripts` (get_transcripts.py)**
- ✅ Batch transcript fetching
- ✅ Enhanced processing with:
  - Natural language segmentation
  - Keyword extraction
  - Summarization
  - Speaker segment identification
- ✅ Formatted with timestamps `[MM:SS]`
- ✅ Language detection

**C. `ScriptGeneratorAgent`**
- ✅ Converts course content → video scripts
- ✅ Audio generation (ElevenLabs integration)
- ✅ Quality checking

#### 2. **Current Scheduler** (`/schedulers/pipelines/`)

**A. `youtube.py`**
- ✅ Fetches latest videos by channel
- ✅ Resolves @handles and channel IDs
- ✅ Rate limiting
- ⚠️ Returns only: title, URL, publishedAt, channelTitle
- ❌ **NO transcript fetching**

**B. `daily_run.py`**
- ✅ Orchestrates all fetchers
- ✅ Gemini AI triage
- ⚠️ Shallow summaries (no full content)

---

## 🔗 INTEGRATION STRATEGY

### Phase 1: Add Transcript Fetching to Scheduler

**Create:** `pipelines/transcript_fetcher.py`

```python
# Standalone module that uses YouTubeAgency's logic
# No dependencies on agency_swarm framework

import os
import sys
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional

# Use youtube_transcript_api directly (already in requirements)
from youtube_transcript_api import YouTubeTranscriptApi

class TranscriptFetcher:
    """
    Fetch YouTube transcripts for scheduler pipeline.
    Based on YouTubeAgency/fetch_video_transcript.py
    """

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or Path(__file__).parents[1] / "outputs" / "transcripts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)',
            r'(?:youtube\.com\/embed\/)([\w-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def fetch_transcript(self, video_url: str) -> Dict:
        """
        Fetch full transcript for a video.

        Returns:
        {
            "video_id": "abc123",
            "transcript": "Full text...",
            "segments": [{"time": 0, "text": "..."}],
            "word_count": 5000,
            "duration_seconds": 600
        }
        """
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return {"error": f"Invalid URL: {video_url}"}

        # Check cache first
        cache_path = self.output_dir / f"{video_id}.txt"
        if cache_path.exists():
            with open(cache_path, 'r') as f:
                cached_text = f.read()
            return {
                "video_id": video_id,
                "transcript": cached_text,
                "word_count": len(cached_text.split()),
                "cached": True
            }

        try:
            # Use YouTube Transcript API
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

            # Extract segments and full text
            segments = []
            full_text_parts = []

            for item in transcript_list:
                segments.append({
                    "time": item['start'],
                    "text": item['text']
                })
                full_text_parts.append(item['text'])

            full_text = " ".join(full_text_parts)

            # Cache the result
            with open(cache_path, 'w') as f:
                f.write(full_text)

            return {
                "video_id": video_id,
                "transcript": full_text,
                "segments": segments,
                "word_count": len(full_text.split()),
                "duration_seconds": transcript_list[-1]['start'] if transcript_list else 0,
                "cached": False
            }

        except Exception as e:
            return {
                "video_id": video_id,
                "error": str(e),
                "transcript": None
            }
```

---

### Phase 2: Enhanced Triage with Transcript Analysis

**Update:** `pipelines/daily_run.py`

```python
from pipelines.transcript_fetcher import TranscriptFetcher

# Initialize fetcher
transcript_fetcher = TranscriptFetcher()

def analyze_video_with_transcript(video_data: dict) -> dict:
    """
    Deep analysis of video using full transcript.

    Input: {"title": "...", "url": "...", "source": "YouTube"}
    Output: Enhanced with transcript analysis
    """

    # Fetch transcript
    transcript_data = transcript_fetcher.fetch_transcript(video_data['url'])

    if transcript_data.get('error'):
        # No transcript available, return basic data
        return video_data

    # Use Gemini to analyze the full transcript
    prompt = f"""
    Analyze this YouTube video transcript and provide:

    1. Quality Score (0-10): Based on depth, credibility, production value
    2. Main Topic: Single sentence
    3. Key Insights: 3-5 bullet points of actionable takeaways
    4. Content Type: Tutorial, News, Opinion, Research, etc.
    5. Target Audience: Beginner, Intermediate, Advanced
    6. Unique Value: What makes this content special?

    Video Title: {video_data['title']}
    Transcript ({transcript_data['word_count']} words):
    {transcript_data['transcript'][:3000]}...

    Return as JSON.
    """

    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )

    analysis = json.loads(response.text)

    return {
        **video_data,
        "quality_score": analysis.get("quality_score", 5),
        "main_topic": analysis.get("main_topic", ""),
        "key_insights": analysis.get("key_insights", []),
        "content_type": analysis.get("content_type", "General"),
        "target_audience": analysis.get("target_audience", "General"),
        "unique_value": analysis.get("unique_value", ""),
        "transcript_word_count": transcript_data['word_count'],
        "has_transcript": True
    }
```

---

### Phase 3: Video Script Generator

**Create:** `pipelines/video_script_generator.py`

```python
import json
from pathlib import Path
from datetime import datetime
import google.generativeai as genai

class VideoScriptGenerator:
    """
    Generates 30-60 second video scripts from daily reports.
    Uses full transcripts for context and quality.
    """

    def __init__(self, model):
        self.model = model
        self.output_dir = Path(__file__).parents[1] / "outputs" / "scripts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_script(self, report_data: dict) -> dict:
        """
        Create video script from top 3 items in report.

        Args:
            report_data: The final_report dict from daily_run.py

        Returns:
            {
                "script": "Full script text...",
                "timecoded_segments": [...],
                "b_roll_suggestions": [...],
                "metadata": {...}
            }
        """

        # Get top 3 items sorted by quality score
        all_items = []
        for topic, items in report_data.items():
            for item in items:
                if item.get('quality_score', 0) > 6:  # Only high quality
                    all_items.append(item)

        # Sort by quality score
        all_items.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        top_3 = all_items[:3]

        if len(top_3) < 3:
            return {"error": "Not enough high-quality items for script"}

        # Build context from transcripts and insights
        context = []
        for item in top_3:
            context.append({
                "title": item['title'],
                "source": item['source'],
                "key_insights": item.get('key_insights', []),
                "unique_value": item.get('unique_value', ''),
                "url": item['url']
            })

        # Generate script
        prompt = f"""
        Create a compelling 45-second video script for a daily tech news brief.

        Today's Top Stories:
        {json.dumps(context, indent=2)}

        Requirements:
        - Opening Hook (5 seconds): Attention-grabbing question or statement
        - Story 1 (12 seconds): Most important/surprising finding
        - Story 2 (12 seconds): Trending topic with impact
        - Story 3 (12 seconds): Actionable insight or future implication
        - Call to Action (4 seconds): Subscribe for daily AI insights

        Format as JSON:
        {{
            "hook": "...",
            "story_1": {{
                "script": "...",
                "b_roll": ["suggestion 1", "suggestion 2"]
            }},
            "story_2": {{...}},
            "story_3": {{...}},
            "cta": "..."
        }}

        Tone: Energetic, authoritative, conversational
        Target: AI practitioners and tech enthusiasts
        Voice: Second person ("You")
        """

        response = self.model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )

        script_data = json.loads(response.text)

        # Create full script
        full_script = self._format_full_script(script_data)

        # Save outputs
        timestamp = datetime.utcnow().strftime("%Y-%m-%d")
        script_path = self.output_dir / f"{timestamp}-script.txt"
        json_path = self.output_dir / f"{timestamp}-storyboard.json"

        with open(script_path, 'w') as f:
            f.write(full_script)

        with open(json_path, 'w') as f:
            json.dump({
                "script": full_script,
                "timecoded": script_data,
                "sources": [item['url'] for item in top_3],
                "generated_at": datetime.utcnow().isoformat()
            }, f, indent=2)

        return {
            "script": full_script,
            "script_path": str(script_path),
            "storyboard_path": str(json_path),
            "sources": top_3
        }

    def _format_full_script(self, data: dict) -> str:
        """Format the JSON script into readable text."""
        sections = [
            "[HOOK - 0:00-0:05]",
            data['hook'],
            "",
            "[STORY 1 - 0:05-0:17]",
            data['story_1']['script'],
            f"B-ROLL: {', '.join(data['story_1']['b_roll'])}",
            "",
            "[STORY 2 - 0:17-0:29]",
            data['story_2']['script'],
            f"B-ROLL: {', '.join(data['story_2']['b_roll'])}",
            "",
            "[STORY 3 - 0:29-0:41]",
            data['story_3']['script'],
            f"B-ROLL: {', '.join(data['story_3']['b_roll'])}",
            "",
            "[CTA - 0:41-0:45]",
            data['cta']
        ]
        return "\n".join(sections)
```

---

### Phase 4: Update GitHub Workflow

**Create:** `.github/workflows/video-script.yml`

```yaml
name: Daily Video Script Generation

on:
  schedule:
    - cron: "0 8 * * *"  # 1 hour after daily report
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  generate-script:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Pull latest reports
        run: git pull

      - name: Generate video script
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python pipelines/generate_video_script.py

      - name: Commit and push script
        run: |
          git config --global user.name "GitHub Actions Bot"
          git config --global user.email "actions-bot@users.noreply.github.com"
          git add outputs/scripts/*.txt outputs/scripts/*.json || true
          git commit -m "Daily video script for $(date -u +'%Y-%m-%d')" || echo "No changes"
          git push
```

**Create:** `pipelines/generate_video_script.py`

```python
#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from datetime import datetime
import google.generativeai as genai

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipelines.video_script_generator import VideoScriptGenerator

# Setup Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not set")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# Load today's report
timestamp = datetime.utcnow().strftime("%Y-%m-%d")
report_path = Path(__file__).parents[1] / "outputs" / "daily" / f"{timestamp}.json"

if not report_path.exists():
    print(f"ERROR: No report found for {timestamp}")
    sys.exit(1)

with open(report_path, 'r') as f:
    report_data = json.load(f)

# Generate script
generator = VideoScriptGenerator(model)
result = generator.generate_daily_script(report_data)

if "error" in result:
    print(f"ERROR: {result['error']}")
    sys.exit(1)

print(f"SUCCESS: Video script generated")
print(f"Script: {result['script_path']}")
print(f"Storyboard: {result['storyboard_path']}")
```

---

## 🚀 IMPLEMENTATION STEPS

### Week 1: Core Integration

1. ✅ Add `youtube-transcript-api` to requirements.txt (already done)
2. Create `pipelines/transcript_fetcher.py`
3. Test transcript fetching for sample videos
4. Update `daily_run.py` to use transcripts for top 5 videos only (quota management)

### Week 2: Enhanced Quality Scoring

1. Modify `triage_and_categorize_content()` to accept transcript data
2. Add quality scoring prompt with full content analysis
3. Filter out low-quality items (<6 score)
4. Update markdown/JSON output to include scores

### Week 3: Video Script Generator

1. Create `pipelines/video_script_generator.py`
2. Create `pipelines/generate_video_script.py` CLI
3. Test script generation locally
4. Add `.github/workflows/video-script.yml`

### Week 4: Polish & Optimization

1. Add transcript caching to reduce API calls
2. Implement smart selection (top 5 videos by engagement)
3. Add error handling and fallbacks
4. Create monitoring/metrics dashboard

---

## 📦 UPDATED REQUIREMENTS.TXT

```txt
requests
beautifulsoup4
PyYAML
python-dotenv
google-generativeai
httpx
youtube-transcript-api  # ← Already compatible with YouTubeAgency
lxml  # For better HTML/XML parsing
```

---

## 🎯 KEY BENEFITS

1. **No Duplication**: Reuses YouTubeAgency logic without importing agency_swarm
2. **Standalone**: Scheduler remains independent
3. **Proven Code**: Leverages tested transcript fetching
4. **Scalable**: Easy to add more YouTubeAgency features later
5. **Quality Boost**: Deep analysis vs shallow summaries

---

## Next Steps

Would you like me to:
1. **Implement the transcript fetcher module** (standalone, no agency_swarm deps)
2. **Create the video script generator**
3. **Add quality scoring with transcript analysis**
4. **All of the above** (complete integration)

Choose your priority and I'll start building! 🚀

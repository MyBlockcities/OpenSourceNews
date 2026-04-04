"""
Video Script Generator
Automatically creates 30-60 second video scripts from daily research reports
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class VideoScriptGenerator:
    """
    Generates compelling video scripts from top research items.
    Designed for daily tech news brief format (30-60 seconds).
    """

    def __init__(self, model):
        """
        Args:
            model: Initialized Gemini model instance
        """
        self.model = model
        self.output_dir = Path(__file__).parents[1] / "outputs" / "scripts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_script(self, report_data: Dict) -> Dict:
        """
        Create video script from top 3 items in daily report.

        Args:
            report_data: The final_report dict from daily_run.py
                        Format: {"Topic Name": [items...], ...}

        Returns:
            {
                "script": "Full formatted script text...",
                "script_path": "/path/to/script.txt",
                "storyboard_path": "/path/to/storyboard.json",
                "sources": [item1, item2, item3],
                "metadata": {...}
            }
        """

        # Collect all items and sort by quality score
        all_items = []
        for topic, items in report_data.items():
            for item in items:
                all_items.append({**item, "topic": topic})

        if len(all_items) == 0:
            return {"error": "No items found in report"}

        # Try to get items with quality scores first (transcript analysis worked)
        scored_items = [item for item in all_items if 'quality_score' in item]

        if scored_items:
            # Sort by quality score and take high-quality ones
            scored_items.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
            high_quality = [item for item in scored_items if item.get('quality_score', 0) >= 7]

            if len(high_quality) >= 3:
                top_3 = high_quality[:3]
                print(f"✓ Using {len(high_quality)} high-quality items (score >= 7)")
            elif len(scored_items) >= 3:
                top_3 = scored_items[:3]
                print(f"✓ Using top {len(top_3)} scored items (avg score: {sum(i.get('quality_score', 0) for i in top_3)/3:.1f})")
            else:
                # Mix scored items with unscored
                top_3 = scored_items[:3]
                print(f"⚠ Only {len(scored_items)} scored items. Mixing with unscored items...")
        else:
            # No quality scores available - use all items and select by relevance
            print("⚠ No quality scores found (transcript analysis failed). Using fallback selection...")
            # Prioritize YouTube videos as they're typically richer content
            youtube_items = [item for item in all_items if item.get('source') == 'YouTube']
            other_items = [item for item in all_items if item.get('source') != 'YouTube']

            top_3 = (youtube_items + other_items)[:3]

        if len(top_3) < 3:
            print(f"⚠ WARNING: Only {len(top_3)} items available for script generation")
            # Use whatever we have
            top_3 = all_items[:3]

        if len(top_3) == 0:
            return {"error": "No items available for script generation"}

        # Build context from items
        context = []
        for idx, item in enumerate(top_3, 1):
            context.append({
                "number": idx,
                "title": item.get('title', 'Unknown'),
                "source": item.get('source', 'Unknown'),
                "category": item.get('category', 'General'),
                "key_insights": item.get('key_insights', []),
                "unique_value": item.get('unique_value', ''),
                "main_topic": item.get('main_topic', ''),
                "quality_score": item.get('quality_score', 0),
                "url": item.get('url', '')
            })

        # Generate script using Gemini
        script_data = self._generate_script_with_ai(context)

        if not script_data:
            return {"error": "Failed to generate script"}

        # Format into full script
        full_script = self._format_full_script(script_data)

        # Save outputs
        timestamp = datetime.utcnow().strftime("%Y-%m-%d")
        script_path = self.output_dir / f"{timestamp}-script.txt"
        json_path = self.output_dir / f"{timestamp}-storyboard.json"

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(full_script)

        storyboard_data = {
            "date": timestamp,
            "script": full_script,
            "timecoded_segments": script_data,
            "sources": [
                {"title": item['title'], "url": item['url'], "quality_score": item.get('quality_score', 0)}
                for item in top_3
            ],
            "generated_at": datetime.utcnow().isoformat(),
            "total_duration_seconds": 50
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(storyboard_data, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "script": full_script,
            "script_path": str(script_path),
            "storyboard_path": str(json_path),
            "sources": top_3,
            "metadata": {
                "date": timestamp,
                "num_sources": len(top_3),
                "avg_quality_score": sum(item.get('quality_score', 0) for item in top_3) / len(top_3),
                "generated_at": datetime.utcnow().isoformat(),
            }
        }

    def _generate_script_with_ai(self, context: List[Dict]) -> Dict:
        """Use Gemini to generate the script structure."""

        prompt = f"""
Create a compelling 50-second video script for a daily AI & Tech news brief.

Today's Top Stories (sorted by quality):
{json.dumps(context, indent=2)}

Create a script with these exact segments:

1. HOOK (5 seconds): Attention-grabbing question or bold statement about today's biggest story
2. STORY 1 (13 seconds): Cover the highest-rated story with its key insight and impact
3. STORY 2 (13 seconds): Second story - focus on what makes it unique/important
4. STORY 3 (13 seconds): Third story - tie it to future implications or actionable takeaways
5. CTA (6 seconds): Call to action for viewers (subscribe, comment with thoughts, etc.)

Requirements:
- Energetic, conversational tone (speak directly to viewer using "you")
- Use specific numbers, names, and facts from the key_insights
- Make it feel urgent and important (FOMO-inducing)
- Each story should have 2-3 B-roll suggestions (screenshots, stock footage, graphics)
- Avoid generic phrases like "in today's news" - jump straight to the insight

Return as valid JSON:
{{
    "hook": "...",
    "story_1": {{
        "script": "...",
        "b_roll": ["suggestion 1", "suggestion 2", "suggestion 3"]
    }},
    "story_2": {{
        "script": "...",
        "b_roll": ["suggestion 1", "suggestion 2", "suggestion 3"]
    }},
    "story_3": {{
        "script": "...",
        "b_roll": ["suggestion 1", "suggestion 2", "suggestion 3"]
    }},
    "cta": "..."
}}
"""

        try:
            response = self.model.generate_content(prompt)

            text_response = getattr(response, 'text', None)
            if not text_response and response.candidates:
                text_response = response.candidates[0].content.parts[0].text

            if text_response:
                # Extract JSON from markdown code blocks if present
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text_response, re.DOTALL)
                if json_match:
                    text_response = json_match.group(1)

                return json.loads(text_response)

        except Exception as e:
            print(f"ERROR: Script generation failed: {e}")
            return None

    def _format_full_script(self, data: Dict) -> str:
        """Format the JSON script into readable, production-ready text."""

        sections = [
            "=" * 60,
            "DAILY AI & TECH NEWS BRIEF",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "Duration: ~50 seconds",
            "=" * 60,
            "",
            "[HOOK - 0:00-0:05]",
            data.get('hook', ''),
            "",
            "[STORY 1 - 0:05-0:18]",
            data.get('story_1', {}).get('script', ''),
            "",
            "B-ROLL:",
            *[f"  - {b}" for b in data.get('story_1', {}).get('b_roll', [])],
            "",
            "[STORY 2 - 0:18-0:31]",
            data.get('story_2', {}).get('script', ''),
            "",
            "B-ROLL:",
            *[f"  - {b}" for b in data.get('story_2', {}).get('b_roll', [])],
            "",
            "[STORY 3 - 0:31-0:44]",
            data.get('story_3', {}).get('script', ''),
            "",
            "B-ROLL:",
            *[f"  - {b}" for b in data.get('story_3', {}).get('b_roll', [])],
            "",
            "[CALL TO ACTION - 0:44-0:50]",
            data.get('cta', ''),
            "",
            "=" * 60,
            "END OF SCRIPT",
            "=" * 60
        ]

        return "\n".join(sections)

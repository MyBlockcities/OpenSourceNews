#!/usr/bin/env python3
"""
Weekly Intelligence Analyzer
Analyzes daily reports from the past week and extracts the best nuggets
for creating "This Week in AI" videos
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
import google.generativeai as genai
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / '.env')
load_dotenv(ROOT_DIR / '.env.local')

OUTPUT_DIR = ROOT_DIR / 'outputs'


def load_week_reports(days_back=7):
    """Load daily reports for the past week"""
    reports = []
    today = datetime.utcnow()
    
    for i in range(days_back):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        report_path = OUTPUT_DIR / 'daily' / f"{date_str}.json"
        
        if report_path.exists():
            with open(report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                reports.append({
                    'date': date_str,
                    'data': data
                })
                print(f"✓ Loaded report for {date_str}")
        else:
            print(f"  Report not found for {date_str}")
    
    return reports


def extract_best_nuggets(weekly_data, model):
    """
    Use Gemini to analyze a week of content and extract the best nuggets
    """
    # Flatten all items from all topics across the week
    all_items = []
    for report in weekly_data:
        for topic, items in report['data'].items():
            for item in items:
                all_items.append({
                    **item,
                    'date': report['date'],
                    'topic': topic
                })
    
    print(f"\nAnalyzing {len(all_items)} items from past week...")
    
    # Prepare data for Gemini
    items_summary = json.dumps([
        {
            'title': item.get('title'),
            'summary': item.get('summary', ''),
            'category': item.get('category', ''),
            'source': item.get('source'),
            'date': item.get('date')
        }
        for item in all_items[:50]  # Limit to 50 items for token efficiency
    ], indent=2)

    prompt = f"""You are an expert AI intelligence analyst. Review this week's content and extract the BEST nuggets for a "This Week in AI" video script.

Content from past 7 days:
{items_summary}

Analyze and return JSON with:
{{
    "top_stories": [
        {{
            "title": "Story title",
            "why_important": "1-2 sentence explanation of significance",
            "key_takeaway": "Most actionable insight",
            "category": "Framework|Funding|Research|Tool",
            "priority": 1-10
        }}
    ],
    "emerging_trends": [
        "Trend 1 description",
        "Trend 2 description"
    ],
    "actionable_insights": [
        "Specific action developers can take",
        "Another actionable insight"
    ],
    "week_summary": "2-3 sentence overview of the week in AI"
}}

Focus on:
- Major framework releases
- Significant funding announcements  
- Breakthrough research
- Practical tools developers can use TODAY
- Emerging patterns across multiple stories

Return ONLY valid JSON (no markdown, no code blocks)."""

    try:
        response = model.generate_content(prompt)
        
        # Extract response
        text_response = None
        if hasattr(response, 'text'):
            text_response = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            if hasattr(response.candidates[0], 'content'):
                if hasattr(response.candidates[0].content, 'parts') and response.candidates[0].content.parts:
                    text_response = response.candidates[0].content.parts[0].text

        if not text_response:
            raise ValueError("No response from Gemini")

        # Clean JSON
        text_response = text_response.strip()
        if text_response.startswith('```'):
            text_response = text_response.replace('```json', '').replace('```', '').strip()

        analysis = json.loads(text_response)
        
        # Add full item details for top stories
        for story in analysis.get('top_stories', []):
            # Find matching item
            matching = next(
                (item for item in all_items if item.get('title') == story['title']),
                None
            )
            if matching:
                story['url'] = matching.get('url')
                story['source_type'] = matching.get('source')
        
        return analysis

    except Exception as e:
        print(f"ERROR: Weekly analysis failed: {e}")
        return None


def generate_weekly_script(analysis, all_items):
    """Generate a compelling 'This Week in AI' script from analysis"""
    
    script_parts = []
    
    # Hook
    script_parts.append("🎬 THIS WEEK IN AI")
    script_parts.append("=" * 60)
    script_parts.append(f"\n{analysis.get('week_summary', 'Another groundbreaking week in AI!')}\n")
    
    # Top Stories
    script_parts.append("\n📰 TOP STORIES\n")
    script_parts.append("-" * 60)
    
    top_stories = sorted(
        analysis.get('top_stories', []),
        key=lambda x: x.get('priority', 0),
        reverse=True
    )[:5]  # Top 5
    
    for idx, story in enumerate(top_stories, 1):
        script_parts.append(f"\n[STORY {idx}]: {story.get('title')}")
        script_parts.append(f"Category: {story.get('category', 'General')}")
        script_parts.append(f"Why it matters: {story.get('why_important', 'N/A')}")
        script_parts.append(f"Key takeaway: {story.get('key_takeaway', 'N/A')}")
        if story.get('url'):
            script_parts.append(f"Source: {story['url']}")
        script_parts.append("")
    
    # Emerging Trends
    if analysis.get('emerging_trends'):
        script_parts.append("\n🔮 EMERGING TRENDS\n")
        script_parts.append("-" * 60)
        for trend in analysis['emerging_trends']:
            script_parts.append(f"• {trend}")
        script_parts.append("")
    
    # Actionable Insights
    if analysis.get('actionable_insights'):
        script_parts.append("\n💡 WHAT YOU CAN DO TODAY\n")
        script_parts.append("-" * 60)
        for insight in analysis['actionable_insights']:
            script_parts.append(f"✓ {insight}")
        script_parts.append("")
    
    # Outro
    script_parts.append("\n" + "=" * 60)
    script_parts.append("That's your AI intelligence brief for the week.")
    script_parts.append("Stay ahead of the curve! 🚀")
    
    return "\n".join(script_parts)


def main():
    # Setup Gemini
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    print("=" * 60)
    print("WEEKLY INTELLIGENCE ANALYZER")
    print("=" * 60)

    # Load past week
    weekly_data = load_week_reports(days_back=7)
    
    if not weekly_data:
        print("\nERROR: No reports found for the past week")
        print("Run daily_run.py to generate reports first")
        sys.exit(1)

    print(f"\n✓ Loaded {len(weekly_data)} days of reports")

    # Extract nuggets
    print("\nExtracting best nuggets with Gemini...")
    analysis = extract_best_nuggets(weekly_data, model)
    
    if not analysis:
        print("ERROR: Analysis failed")
        sys.exit(1)

    # Generate script
    print("\nGenerating weekly script...")
    
    # Collect all items for context
    all_items = []
    for report in weekly_data:
        for topic, items in report['data'].items():
            all_items.extend(items)
    
    script = generate_weekly_script(analysis, all_items)

    # Save outputs
    week_end = datetime.utcnow().strftime("%Y-%m-%d")
    analysis_path = OUTPUT_DIR / 'weekly' / f"{week_end}-analysis.json"
    script_path = OUTPUT_DIR / 'weekly' / f"{week_end}-script.txt"
    
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script)

    # Print results
    print("\n" + "=" * 60)
    print("✓ SUCCESS: Weekly analysis complete!")
    print("=" * 60)
    print(f"\nAnalysis: {analysis_path}")
    print(f"Script:   {script_path}")
    
    print(f"\nTop Stories: {len(analysis.get('top_stories', []))}")
    print(f"Emerging Trends: {len(analysis.get('emerging_trends', []))}")
    print(f"Actionable Insights: {len(analysis.get('actionable_insights', []))}")
    
    print("\n" + "=" * 60)
    print("PREVIEW:")
    print("=" * 60)
    print(script)


if __name__ == "__main__":
    main()

import React, { useState } from 'react';
import { TopicIcon } from './icons/TopicIcon';
import { RssIcon } from './icons/RssIcon';
import { YoutubeIcon } from './icons/YoutubeIcon';
import { HackerNewsIcon } from './icons/HackerNewsIcon';
import { GithubIcon } from './icons/GithubIcon';
import { ClipboardIcon } from './icons/ClipboardIcon';
import { TrashIcon } from './icons/TrashIcon';
import { PlusIcon } from './icons/PlusIcon';
import { XIcon } from './icons/XIcon';
import { InstagramIcon } from './icons/InstagramIcon';

type SourceType = 'rss' | 'youtube' | 'github' | 'hackernews' | 'x' | 'instagram';

interface Source {
  type: SourceType;
  value: string;
}

interface Topic {
  name: string;
  sources: Source[];
}

const CodeBlock: React.FC<{ code: string; fileName: string }> = ({ code, fileName }) => {
    const [copied, setCopied] = useState(false);
    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };
    return (
        <div className="bg-gray-900/70 rounded-lg my-4">
            <div className="flex justify-between items-center px-4 py-2 bg-gray-700/50 rounded-t-lg">
                <p className="text-sm font-semibold text-gray-300 font-space-mono">{fileName}</p>
                <button onClick={handleCopy} className="flex items-center gap-2 text-sm text-gray-300 hover:text-white">
                    <ClipboardIcon className="w-4 h-4" />
                    {copied ? 'Copied!' : 'Copy'}
                </button>
            </div>
            <pre className="p-4 text-xs text-gray-200 overflow-x-auto"><code>{code}</code></pre>
        </div>
    );
};


const AutomationHub: React.FC = () => {
    const [topics, setTopics] = useState<Topic[]>([
        { name: 'AI Agents & Frameworks', sources: [{ type: 'github', value: 'typescript' }, { type: 'hackernews', value: 'AI Agent' }] },
        { name: 'Blockchain VC Funding', sources: [{ type: 'rss', value: 'https://www.coindesk.com/arc/outboundfeeds/rss/' }, { type: 'x', value: 'a16zcrypto' }] },
    ]);
    const [schedule, setSchedule] = useState('0 7 * * *'); // Default to 7 AM UTC

    const addTopic = () => setTopics([...topics, { name: 'New Topic', sources: [] }]);
    const removeTopic = (index: number) => setTopics(topics.filter((_, i) => i !== index));
    const handleTopicNameChange = (index: number, name: string) => {
        const newTopics = [...topics];
        newTopics[index].name = name;
        setTopics(newTopics);
    };

    const addSource = (topicIndex: number, type: SourceType) => {
        const newTopics = [...topics];
        newTopics[topicIndex].sources.push({ type, value: '' });
        setTopics(newTopics);
    };
    const removeSource = (topicIndex: number, sourceIndex: number) => {
        const newTopics = [...topics];
        newTopics[topicIndex].sources.splice(sourceIndex, 1);
        setTopics(newTopics);
    };
    const handleSourceValueChange = (topicIndex: number, sourceIndex: number, value: string) => {
        const newTopics = [...topics];
        newTopics[topicIndex].sources[sourceIndex].value = value;
        setTopics(newTopics);
    };

    const sourceInfo: Record<SourceType, { icon: React.FC, placeholder: string, label: string, description?: string }> = {
        rss: { icon: RssIcon, placeholder: 'https://example.com/feed.xml', label: 'RSS Feed' },
        youtube: { icon: YoutubeIcon, placeholder: 'UCZYTClx2T1of7BRZ86-8fow', label: 'YouTube Channel', description: 'Use Channel ID (UC...), not handle (@vrsen).'},
        github: { icon: GithubIcon, placeholder: 'typescript', label: 'GitHub Trending' },
        hackernews: { icon: HackerNewsIcon, placeholder: 'LLM', label: 'Hacker News' },
        x: { icon: XIcon, placeholder: 'karpathy', label: 'X Profile' },
        instagram: { icon: InstagramIcon, placeholder: 'googleai', label: 'Instagram Profile' },
    };

    const generateFeedsYaml = () => {
        let yaml = '# config/feeds.yaml\n\n';
        yaml += 'topics:\n';
        topics.forEach(topic => {
            if (topic.name.trim() === '') return;
            yaml += `  - topic_name: "${topic.name}"\n`;
            const sourcesByType = topic.sources.reduce((acc, source) => {
                if(source.value.trim() === '') return acc;
                const key = `${source.type}_sources`;
                if (!acc[key]) acc[key] = [];
                acc[key].push(source.value);
                return acc;
            }, {} as Record<string, string[]>);

            for (const [key, values] of Object.entries(sourcesByType)) {
                yaml += `    ${key}:\n`;
                (values as string[]).forEach(value => yaml += `      - "${value}"\n`);
            }
        });
        return yaml;
    };
    
    const generateRequirementsTxt = () => `requests
beautifulsoup4
PyYAML
python-dotenv
google-generativeai

# --- OPTIONAL: For X/Twitter Integration (implement fetcher in daily_run.py) ---
# tweepy

# --- OPTIONAL: For Instagram Integration (use with caution, may be unstable) ---
# instaloader`;

    const generateDailyRunPy = () => `import os
import yaml
import json
import datetime
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import google.generativeai as genai

# --- CONFIGURATION ---
ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / 'config' / 'feeds.yaml'
OUTPUT_DIR = ROOT_DIR / 'outputs' / 'daily'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- HTTP DEFAULTS ---
HTTP_TIMEOUT = 20
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (research-bot; +https://github.com/user/repo)"
}

# --- GEMINI SETUP ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
else:
    print("WARNING: GEMINI_API_KEY not found. Triage agent will be skipped.")

# --- HELPERS ---
def _get(url: str):
    r = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r

# --- DATA FETCHERS ---
def fetch_rss(url: str, limit: int = 5):
    if not url: return []
    try:
        resp = _get(url)
        soup = BeautifulSoup(resp.content, "xml")
        items = []
        for item in soup.find_all("item")[:limit]:
            title = (item.title.text if item.title else "").strip()
            link = (item.link.text if item.link else "").strip()
            if title and link:
                items.append({"title": title, "url": link, "source": "RSS"})
        return items
    except Exception as e:
        print(f"ERROR: RSS fetch failed for {url}: {e}")
        return []

def fetch_youtube_channel(channel_id: str):
    if not channel_id: return []
    print(f"INFO: Skipping YouTube placeholder for Channel ID '{channel_id}'. Implement with YouTube Data API.")
    # To implement: Use googleapiclient to search for recent videos by channelId.
    # This requires a YouTube Data API key.
    return []

def fetch_github_trending(language: str):
    if not language: return []
    url = f"https://github.com/trending/{language}"
    try:
        resp = _get(url)
        soup = BeautifulSoup(resp.content, "html.parser")
        items = []
        for repo in soup.select("article.Box-row")[:5]:
            a_tag = repo.select_one("h2 > a")
            if not a_tag: continue
            title = " ".join(a_tag.text.split())
            href = a_tag.get("href", "")
            if href:
                items.append({"title": title, "url": f"https://github.com{href}", "source": "GitHub Trending"})
        return items
    except Exception as e:
        print(f"ERROR: GitHub trending fetch for '{language}' failed: {e}")
        return []

def fetch_hackernews(keyword: str):
    if not keyword: return []
    url = f"https://hn.algolia.com/api/v1/search?query={keyword}&tags=story"
    try:
        hits = _get(url).json().get("hits", [])
        items = []
        for hit in hits[:5]:
            title, link = hit.get("title"), hit.get("url")
            if title and link:
                items.append({"title": title, "url": link, "source": "Hacker News"})
        return items
    except Exception as e:
        print(f"ERROR: Hacker News fetch for '{keyword}' failed: {e}")
        return []

def fetch_x_profile_posts(username: str):
    if not username: return []
    print(f"INFO: Skipping X placeholder for @{username}. Implement with official X API.")
    return []

def fetch_instagram_profile_posts(username: str):
    if not username: return []
    print(f"INFO: Skipping Instagram placeholder for @{username}.")
    return []

# --- AI TRIAGE AGENT ---
def triage_and_categorize_content(topic_name: str, items: list) -> list:
    if not items:
        return []
    
    print(f"Running Triage Agent for topic: '{topic_name}' ({len(items)} items)")

    # Fallback if Gemini is not configured
    def fallback_triage(item_list):
        return [
            {**item, "category": "General News", "summary": ""}
            for item in item_list
        ]

    if not model:
        return fallback_triage(items)

    prompt = f"""
    You are a Triage Analyst. Review the following items for the topic '{topic_name}'.
    Return ONLY a JSON array of objects. Each object must have:
    - "title": string
    - "url": string
    - "source": string
    - "category": string (one of: "Funding Announcement", "New Framework Release", "Major Partnership", "Technical Analysis", "General News")
    - "summary": string (a concise, 1-2 sentence summary)
    
    Raw items:
    {json.dumps(items, ensure_ascii=False)}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        # Handle potential variations in Gemini SDK response structure
        text_response = getattr(response, 'text', None)
        if not text_response and response.candidates:
             text_response = response.candidates[0].content.parts[0].text
        
        if text_response:
             parsed_json = json.loads(text_response)
             if isinstance(parsed_json, list):
                 return parsed_json
    except Exception as e:
        print(f"ERROR: Gemini triage API call failed: {e}. Using fallback.")
    
    return fallback_triage(items)


# --- MAIN ORCHESTRATOR ---
def main():
    with open(CONFIG_PATH, 'r', encoding="utf-8") as f:
        config = yaml.safe_load(f)

    final_report = {}
    
    fetcher_map = {
        'rss_sources': fetch_rss,
        'youtube_sources': fetch_youtube_channel,
        'github_sources': fetch_github_trending,
        'hackernews_sources': fetch_hackernews,
        'x_sources': fetch_x_profile_posts,
        'instagram_sources': fetch_instagram_profile_posts,
    }

    for topic in config.get('topics', []):
        topic_name = topic.get('topic_name', 'Unnamed Topic')
        print(f"\\n--- Processing Topic: {topic_name} ---")
        all_raw_content = []
        for source_type, fetcher_func in fetcher_map.items():
            for source_value in topic.get(source_type, []) or []:
                try:
                    fetched_items = fetcher_func(source_value)
                    if fetched_items:
                        all_raw_content.extend(fetched_items)
                except Exception as e:
                    print(f"ERROR: Failed during fetch for {source_type} '{source_value}': {e}")
        
        triaged_content = triage_and_categorize_content(topic_name, all_raw_content)
        final_report[topic_name] = triaged_content

    # --- SAVE REPORT ---
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    report_path = OUTPUT_DIR / f"{timestamp}.json"
    with open(report_path, 'w', encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    print(f"\\nSUCCESS: Daily intelligence report saved to {report_path}")

if __name__ == "__main__":
    main()
`;
    
    const generateGithubActionYml = () => `name: Daily Research Briefing
on:
  schedule:
    - cron: "${schedule}" # Runs at ${schedule} UTC
  workflow_dispatch: {} # Allows manual runs

permissions:
  contents: write # Needed to commit the report back to the repo

concurrency:
  group: daily-research
  cancel-in-progress: false

jobs:
  run-research:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: \${{ runner.os }}-pip-\${{ hashFiles('**/requirements.txt') }}
          restore-keys: |
            \${{ runner.os }}-pip-

      - name: Install dependencies
        run: pip install -r requirements.txt
        
      - name: Run research pipeline
        env:
          GEMINI_API_KEY: \${{ secrets.GEMINI_API_KEY }}
          # X_CONSUMER_KEY: \${{ secrets.X_CONSUMER_KEY }}
          # X_CONSUMER_SECRET: \${{ secrets.X_CONSUMER_SECRET }}
          # Add other secrets for social media APIs here
        run: python pipelines/daily_run.py
        
      - name: Commit and push report
        run: |
          git config --global user.name "GitHub Actions Bot"
          git config --global user.email "actions-bot@users.noreply.github.com"
          git add outputs/daily/*.json || true
          git commit -m "Daily intelligence report for $(date -u +'%Y-%m-%d')" || echo "No changes to commit"
          git push
`;

    return (
        <div className="animate-fade-in">
            <div className="text-center mb-10">
                <h2 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-green-400 font-space-mono mb-2">Automation Hub</h2>
                <p className="text-gray-400 max-w-2xl mx-auto">Design and generate an autonomous, scheduled research agent. Configure your topics and sources, then deploy it with GitHub Actions.</p>
            </div>

            {/* Step 1: Configuration */}
            <div className="bg-gray-800/30 rounded-lg p-6 mb-8 border border-gray-700">
                <h3 className="text-2xl font-bold text-gray-200 mb-5 font-space-mono">Step 1: Configure Your Agent</h3>
                
                <div className="mb-6">
                    <label className="block text-lg font-semibold text-gray-300 mb-2">Schedule (UTC Cron)</label>
                    <input type="text" value={schedule} onChange={e => setSchedule(e.target.value)} className="font-space-mono bg-gray-900 border border-gray-600 rounded-md px-3 py-2 text-gray-200 w-full md:w-1/2" />
                    <p className="text-xs text-gray-500 mt-1">Default is 7:00 AM UTC daily. <a href="https://crontab.guru/" target="_blank" rel="noopener noreferrer" className="underline">Need help?</a></p>
                </div>

                {topics.map((topic, topicIndex) => (
                    <div key={topicIndex} className="bg-gray-900/50 p-4 rounded-lg border border-gray-700 mb-4">
                        <div className="flex justify-between items-center mb-4">
                            <div className="flex items-center gap-3 flex-grow">
                                <TopicIcon />
                                <input type="text" value={topic.name} onChange={e => handleTopicNameChange(topicIndex, e.target.value)} className="text-xl font-bold bg-transparent border-b border-gray-600 focus:border-cyan-500 focus:outline-none text-gray-200 flex-grow" />
                            </div>
                            <button onClick={() => removeTopic(topicIndex)} className="text-gray-500 hover:text-red-400"><TrashIcon /></button>
                        </div>
                        
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            {topic.sources.map((source, sourceIndex) => {
                                const Info = sourceInfo[source.type];
                                return (
                                <div key={sourceIndex}>
                                    <div className="flex items-center gap-2 bg-gray-800/60 p-2 rounded-md">
                                        <Info.icon />
                                        <input type="text" value={source.value} onChange={e => handleSourceValueChange(topicIndex, sourceIndex, e.target.value)} placeholder={Info.placeholder} className="flex-grow bg-transparent text-sm text-gray-300 focus:outline-none" />
                                        <button onClick={() => removeSource(topicIndex, sourceIndex)} className="text-gray-600 hover:text-red-400"><TrashIcon className="w-4 h-4"/></button>
                                    </div>
                                    {Info.description && <p className="text-xs text-gray-500 mt-1 pl-1">{Info.description}</p>}
                                </div>
                                )
                            })}
                        </div>

                        <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-700/50">
                            {(Object.keys(sourceInfo) as SourceType[]).map(type => (
                                <button key={type} onClick={() => addSource(topicIndex, type)} className="flex items-center gap-2 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 font-semibold px-3 py-1.5 rounded-md">
                                    <PlusIcon className="w-3 h-3"/> Add {sourceInfo[type].label}
                                </button>
                            ))}
                        </div>
                    </div>
                ))}
                 <button onClick={addTopic} className="flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 font-bold mt-4">
                    <PlusIcon className="w-4 h-4" /> Add Research Topic
                </button>
            </div>

             {/* Step 2: Generated Code */}
             <div className="bg-gray-800/30 rounded-lg p-6 mb-8 border border-gray-700">
                <h3 className="text-2xl font-bold text-gray-200 mb-5 font-space-mono">Step 2: Get Your Code</h3>
                <p className="text-gray-400 mb-4">Based on your configuration, here are the files for your autonomous agent. Copy them into your own GitHub repository.</p>
                <CodeBlock fileName=".github/workflows/daily.yml" code={generateGithubActionYml()} />
                <CodeBlock fileName="pipelines/daily_run.py" code={generateDailyRunPy()} />
                <CodeBlock fileName="config/feeds.yaml" code={generateFeedsYaml()} />
                <CodeBlock fileName="requirements.txt" code={generateRequirementsTxt()} />
            </div>

            {/* Step 3: Deployment */}
            <div className="bg-gray-800/30 rounded-lg p-6 border border-gray-700">
                <h3 className="text-2xl font-bold text-gray-200 mb-5 font-space-mono">Step 3: Deploy to GitHub</h3>
                <ol className="list-decimal list-inside space-y-3 text-gray-300">
                    <li>Create a new, private GitHub repository.</li>
                    <li>Create the folder structure inside: `pipelines/`, `config/`, `.github/workflows/`.</li>
                    <li>Copy the generated code above into the corresponding files in your repository.</li>
                    <li>Go to your repository's **Settings &gt; Secrets and variables &gt; Actions**.</li>
                    <li>Click **New repository secret** and add only the provider keys you intend to use.</li>
                    <li>If using X or Instagram, add their API keys as secrets (e.g., `X_CONSUMER_KEY`) and implement the logic in `pipelines/daily_run.py`.</li>
                    <li>Commit and push the files. The action will run on your defined schedule, or you can trigger it manually from the "Actions" tab.</li>
                </ol>
            </div>
        </div>
    );
};

export default AutomationHub;

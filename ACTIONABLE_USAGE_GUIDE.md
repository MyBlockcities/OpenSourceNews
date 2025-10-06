# Actionable Intelligence System - Usage Guide

**Date:** October 6, 2025  
**Status:** ✅ Fully Operational & Deployed  
**Purpose:** Turn collected intelligence into action  

---

## 🎯 Quick Start - Make It Actionable

### 1. View Your Daily Intelligence (FREE)

```bash
# Start the frontend
cd /Users/brians/Documents/agency_swarm_openaisdk/schedulers
npm run dev

# Open browser
http://localhost:5173

# Click "Daily Feed" tab
```

**What You See:**
- Last 2 days of collected intelligence
- AI Agents & Blockchain topics
- 19 curated items with summaries
- All FREE to browse

---

### 2. Select Items for Your Video (FREE)

**Click checkboxes to select interesting items:**

☑️ "New ways to build with Jules" (Google AI)  
☑️ "Agentic Design Methodology with Parlant" (MarkTechPost)  
☐ "How to Evaluate Voice Agents" (MarkTechPost)  
☑️ "Google Proposes TUMIX" (Google AI)  

**Selection Tools:**
- Click item OR checkbox to select
- "Select All" button - choose all items
- "Clear All" button - deselect everything
- Selected count shows: "(3 selected)"

**Cost: $0** (selection is free)

---

### 3. Generate Video Script (FREE)

**After selecting 2-5 items:**

1. Click `Generate Script (N)` button
2. Wait ~2 seconds (instant, local generation)
3. Script appears below with:
   - Formatted story structure
   - Key insights highlighted
   - Source links included
   - Ready to copy/edit

**Sample Output:**
```
🎬 THIS WEEK IN AI - Your Weekly Intelligence Brief

[STORY 1]: New ways to build with Jules, our AI coding agent
Google introduces Jules, an AI coding agent, offering new tools...

Source: RSS - https://blog.google/technology/google-labs/...

[STORY 2]: Agentic Design Methodology...
...

That's all for this week's AI intelligence brief!
```

**Cost: $0** (local generation, no API calls)

---

### 4. Weekly "This Week in AI" Analysis

**For a comprehensive weekly summary with best nuggets:**

```bash
cd /Users/brians/Documents/agency_swarm_openaisdk/schedulers

# Run weekly analyzer
python3 pipelines/weekly_analyzer.py
```

**What It Does:**
1. Loads past 7 days of daily reports
2. Analyzes ALL items (50-100+ items)
3. Extracts:
   - 🏆 Top 5 stories (prioritized by importance)
   - 🔮 Emerging trends (patterns across multiple days)
   - 💡 Actionable insights (what YOU can do)
   - 📝 Week summary (2-3 sentence overview)

**Output:**
```
outputs/weekly/2025-10-05-analysis.json  (structured data)
outputs/weekly/2025-10-05-script.txt     (formatted script)
```

**Sample Weekly Script:**
```
🎬 THIS WEEK IN AI
============================================================

Another groundbreaking week with major releases from Google, new agentic frameworks, and institutional blockchain funding.

📰 TOP STORIES
------------------------------------------------------------

[STORY 1]: Google Proposes TUMIX
Category: Framework
Why it matters: Novel approach for multi-agent test-time scaling...
Key takeaway: Opens new possibilities for agent orchestration
Source: https://www.marktechpost.com/...

[STORY 2]: Nasdaq, Citi Fund Blockchain Firm Symbiont
Category: Funding
Why it matters: Major institutional investment signals...
Key takeaway: Blockchain legitimacy increasing in traditional finance
Source: https://www.bloomberg.com/...

🔮 EMERGING TRENDS
------------------------------------------------------------
• Multi-agent frameworks moving from research to production
• Institutional capital flowing into blockchain infrastructure
• Agentic workflows replacing traditional automation

💡 WHAT YOU CAN DO TODAY
------------------------------------------------------------
✓ Experiment with Claude Code SDK for custom agents
✓ Explore Kestra as open-source n8n alternative
✓ Monitor blockchain VC funding for market signals

That's your AI intelligence brief for the week. Stay ahead! 🚀
```

**Cost: ~$0.03/week** (Gemini analysis of week's content)

---

## 💡 Workflow Examples

### Use Case 1: Daily Video (2-3 min)

**Goal:** Create a quick daily AI update

**Steps:**
1. Open Daily Feed (today's date)
2. Select 2-3 best items (check boxes)
3. Click "Generate Script (3)"
4. Copy script
5. Record/edit video

**Time:** 5 minutes  
**Cost:** $0  
**Output:** Daily AI update ready to publish

---

### Use Case 2: Weekly Deep Dive (8-10 min)

**Goal:** Create comprehensive "This Week in AI" video

**Steps:**
1. Run: `python3 pipelines/weekly_analyzer.py`
2. Review: `outputs/weekly/YYYY-MM-DD-script.txt`
3. Edit script as needed
4. Add B-roll notes
5. Record video

**Time:** 15 minutes  
**Cost:** $0.03 (Gemini analysis)  
**Output:** Professional weekly AI intelligence video

---

### Use Case 3: Custom Topic Focus

**Goal:** Create a script about "Agentic Frameworks" only

**Steps:**
1. Open Daily Feed
2. Select "AI Agents & Frameworks" topic
3. Check only framework-related items:
   ☑️ "Google Proposes TUMIX"
   ☑️ "The Last Multi-Agent Framework"
   ☑️ "Claude Code 2.0"
4. Generate Script (3)
5. Customize and publish

**Time:** 5 minutes  
**Cost:** $0  
**Output:** Focused topic video

---

### Use Case 4: Newsletter Content

**Goal:** Extract insights for email newsletter

**Steps:**
1. Open Daily Feed
2. Browse all items (no selection needed)
3. Copy summaries you like (built-in)
4. Or generate script and extract key points
5. Format into newsletter

**Time:** 10 minutes  
**Cost:** $0  
**Output:** Newsletter ready to send

---

## 🎬 Script Generation Options

### Option A: Basic (Current - FREE)
**Method:** Local generation in browser  
**Quality:** Good for daily updates  
**Features:**
- Instant generation
- Formatted structure
- Sources included
- Copy-paste ready

**Best for:** Daily videos, quick updates

### Option B: Advanced (Coming Soon - $0.02/script)
**Method:** API with Gemini enhancement  
**Quality:** Professional-grade  
**Features:**
- Compelling storytelling
- Technical depth
- Optimal pacing
- B-roll suggestions

**Best for:** Weekly videos, premium content

---

## 📅 Weekly Analysis Deep Dive

### What Makes It Special:

**Smart Prioritization:**
- Analyzes 50-100 items from 7 days
- Ranks by importance (1-10 scale)
- Identifies cross-day patterns
- Filters noise automatically

**Nugget Extraction:**
```json
{
  "top_stories": [
    {
      "title": "...",
      "why_important": "Significance explained",
      "key_takeaway": "Most actionable insight",
      "priority": 9
    }
  ],
  "emerging_trends": [
    "Multi-agent frameworks going mainstream",
    "Institutional blockchain adoption accelerating"
  ],
  "actionable_insights": [
    "Try Claude Code SDK for agent development",
    "Monitor DeFi funding for market signals"
  ]
}
```

**Value Add:**
- Connects dots across multiple days
- Identifies what matters most
- Surfaces actionable insights
- Saves hours of manual analysis

---

## 💰 Cost Breakdown

### Daily Operations:
| Activity | Cost | Frequency |
|----------|------|-----------|
| Browse feed | $0 | Unlimited |
| Select items | $0 | Unlimited |
| Generate script (local) | $0 | Unlimited |
| Weekly analysis | $0.03 | Once/week |

### Monthly Total:
```
Daily browsing: $0 × 30 = $0
Weekly analysis: $0.03 × 4 = $0.12
Base automation: $0.60
---
Total: $0.72/month (was $30/month!)

Savings: $29.28/month = $350/year
```

---

## 🚀 Advanced Features

### 1. Multi-Day Compilation

**Combine multiple days into one script:**

1. Open Day 1, select 2 items
2. Open Day 2, select 2 items  
3. Open Day 3, select 1 item
4. Generate weekly script from all 5

*(Feature coming soon - for now use weekly_analyzer.py)*

### 2. Topic-Specific Scripts

**Focus on one topic across time:**

1. Always select same topic (e.g., "Blockchain")
2. Select all recent funding announcements
3. Generate "VC Funding This Week" script

### 3. Custom Templates

**Different script formats:**
- Twitter thread (bullet points)
- LinkedIn post (professional)
- Blog article (detailed)
- YouTube shorts (30-sec scripts)

*(Templates coming soon)*

---

## 📊 Quality Metrics

### Script Quality Indicators:

**High-Quality Script Has:**
- ✅ 3-5 stories (not too many/few)
- ✅ Mix of categories (Framework + Funding + Research)
- ✅ Diverse sources (RSS + YouTube + HN)
- ✅ Actionable insights (what viewers can do)
- ✅ Clear narrative flow

**Check Quality:**
- Look at "Avg Quality" score in metadata
- Aim for 7.5+/10 average
- Select higher-scored items for better scripts

---

## 🎯 Best Practices

### Selection Strategy:

**For Daily Videos (2-3 min):**
- Select 2-3 items
- Choose ONE category (focus)
- Pick latest/freshest content
- Aim for 7+/10 quality scores

**For Weekly Videos (8-10 min):**
- Run weekly_analyzer.py
- Review top 5 stories
- Add emerging trends
- Include actionable insights

**For Maximum Engagement:**
- Mix sources (don't all YouTube or all RSS)
- Balance framework + funding + research
- Start with highest priority/quality
- End with actionable takeaway

---

## 🔧 Troubleshooting

### Issue: No reports showing

**Solution:**
```bash
# Generate today's report
python3 pipelines/daily_run.py

# Refresh browser
# Report should appear in dropdown
```

### Issue: Script generation not working

**Check:**
1. At least one item selected? (checkbox checked)
2. Browser console for errors (F12)
3. Try with just 1 item first

**Solution:** Select items, click "Generate Script (N)" button

### Issue: Weekly analysis fails

**Solution:**
```bash
# Ensure you have reports for past 7 days
ls outputs/daily/*.json

# Run daily pipeline if needed
python3 pipelines/daily_run.py

# Then run weekly
python3 pipelines/weekly_analyzer.py
```

---

## 📝 Workflow Checklist

### Daily Workflow (5 min):
- [ ] Open Daily Feed in browser
- [ ] Select today's date
- [ ] Browse AI Agents topic
- [ ] Check 2-3 interesting items
- [ ] Click "Generate Script"
- [ ] Copy script
- [ ] Create video or newsletter

### Weekly Workflow (15 min):
- [ ] Run `python3 pipelines/weekly_analyzer.py`
- [ ] Review `outputs/weekly/*.txt`
- [ ] Edit/customize script
- [ ] Add B-roll notes
- [ ] Create comprehensive video

### Monthly Review (30 min):
- [ ] Review cost (should be <$5)
- [ ] Analyze which sources perform best
- [ ] Adjust feed configuration if needed
- [ ] Plan next month's content strategy

---

## 🎉 Success Stories

### What You Can Create:

**Daily Videos:**
- "AI News in 90 Seconds"
- "Today's Top AI Development"
- "Framework Friday" (weekly)

**Weekly Videos:**
- "This Week in AI" (comprehensive)
- "AI Funding Roundup" (blockchain focus)
- "Tools You Should Try" (practical)

**Written Content:**
- LinkedIn posts (daily)
- Newsletter sections (weekly)
- Blog articles (deep dives)
- Twitter threads (viral format)

---

## 💡 Pro Tips

### Tip 1: Quality Over Quantity
- Better to select 3 great items than 10 mediocre ones
- Use quality scores as guide (7+ recommended)
- Check summaries before selecting

### Tip 2: Mix Your Sources
- Don't select all from one source type
- Combine: RSS (frameworks) + HN (research) + YouTube (tutorials)
- Creates more engaging, diverse content

### Tip 3: Use Categories Strategically
- "New Framework Release" = tool demos
- "Funding Announcement" = market signals
- "Technical Analysis" = deep dives
- Mix categories for balanced content

### Tip 4: Weekly Analysis is Gold
- Run weekly_analyzer.py every Sunday
- Uses AI to find patterns you'd miss
- Extracts THE best nuggets automatically
- Worth the $0.03 cost!

---

## 📈 Maximizing Value

### High-Value Workflows:

**1. Daily Pulse Check (2 min/day)**
- Open feed each morning
- Scan summaries (already categorized!)
- Note interesting items
- Cost: $0

**2. Weekly Content Creation (30 min/week)**
- Run weekly analyzer
- Generate video script
- Record and publish
- Cost: $0.03

**3. Strategic Intelligence (1 hr/month)**
- Review all weekly analyses
- Identify long-term trends
- Plan content strategy
- Inform business decisions
- Cost: $0.12/month

**Annual Value: Intelligence that would cost $1000s from analysts**  
**Your Cost: $0.72/month**

---

## 🚀 Next Steps to Take Action

### This Week:
1. ✅ Browse today's feed (familiarize yourself)
2. ✅ Select 2-3 items and generate a test script
3. ✅ Run weekly analyzer once
4. ✅ Create your first "This Week in AI" video

### This Month:
5. Establish daily browsing habit (5 min/day)
6. Create 2-3 videos from generated scripts
7. Track which sources/topics perform best
8. Refine selection strategy

### Long-term:
9. Build content library from intelligence
10. Develop unique insights/voice
11. Monetize through videos/newsletter
12. Scale content creation

---

## 📊 ROI Analysis

### Time Investment:
- Browse daily: 5 min/day = 2.5 hr/month
- Generate scripts: 10 min/week = 40 min/month
- Create content: 1 hr/week = 4 hr/month
- **Total: ~7 hours/month**

### Value Created:
- Daily videos: 20/month
- Weekly deep dives: 4/month
- Newsletter content: Unlimited
- Strategic intelligence: Priceless

### Cost:
- System: $0.72/month
- Time: 7 hours/month
- **Comparable service: $500-1000/month**

**ROI: 700-1400x return on investment!**

---

## ✨ The Actionable Advantage

### Before This System:
- ❌ Manually browse 50+ sources daily
- ❌ Take notes, categorize, summarize
- ❌ Write scripts from scratch
- ❌ Time: 2-3 hours/day
- ❌ Cost: Your valuable time

### With This System:
- ✅ Auto-collect from 50+ sources daily
- ✅ AI categorizes and summarizes
- ✅ Generate scripts in seconds
- ✅ Time: 15 minutes/day
- ✅ Cost: $0.72/month

**Time Saved: 90%**  
**Quality Improved: Professionally curated**  
**Cost: Near-zero**  

---

## 🎯 Making It YOUR System

### Customize for Your Needs:

**Content Creator:**
- Select viral-worthy stories
- Focus on visual/demo content
- Generate scripts for shorts

**Newsletter Writer:**
- Select diverse, balanced items
- Focus on written summaries
- Extract key insights

**Researcher:**
- Select technical deep-dives
- Focus on papers/frameworks
- Track emerging patterns

**Investor:**
- Select funding announcements
- Focus on blockchain category
- Identify market signals

**The system adapts to YOU!**

---

## 📚 Quick Reference

### Commands:
```bash
# Daily collection (automated at 7 AM UTC)
python3 pipelines/daily_run.py

# Weekly analysis (run manually)
python3 pipelines/weekly_analyzer.py

# Start frontend
npm run dev
# Open: http://localhost:5173 → Daily Feed
```

### File Locations:
```
outputs/daily/YYYY-MM-DD.json    - Daily reports
outputs/weekly/YYYY-MM-DD-*.txt  - Weekly scripts
outputs/scripts/YYYY-MM-DD-*.txt - Generated scripts
```

### Key Features:
- ☑️ Checkboxes - Select items individually
- 📊 Quality scores - Filter by quality
- 🎬 Generate Script - Create from selection
- 📅 Weekly mode - Comprehensive analysis
- 💰 Cost display - Full transparency

---

## 🎉 Bottom Line

You now have a system that:

1. **Collects** intelligence automatically ($0.60/month)
2. **Curates** with AI categorization (100% summaries)
3. **Presents** in clean, browsable UI (FREE)
4. **Enables** selection and curation (checkboxes)
5. **Generates** scripts instantly (FREE local, $0.02 API)
6. **Analyzes** weekly patterns ($0.03/week)
7. **Delivers** actionable insights (priceless)

**The intelligence is now FULLY ACTIONABLE.**

**You can turn it into:**
- ✅ Videos
- ✅ Newsletters
- ✅ Blog posts
- ✅ Social media
- ✅ Business decisions
- ✅ Competitive intelligence

**Cost:** $0.72/month  
**Value:** $1000s/month of analyst work  
**Time Saved:** 90% vs manual  
**Quality:** Professional-grade  

**Your move! 🚀**

---

**Created:** October 6, 2025  
**Status:** Live & Ready to Use  
**Next:** Open the feed and start creating!
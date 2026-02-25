# 🎯 STARCoach

AI-powered STAR interview practice bot for Discord. Join a voice channel, practice behavioral interview questions, and get personalized coaching feedback on your STAR method answers.

**Forked from [StaffLens](https://github.com/chchchadzilla/StaffLens)** — same voice infrastructure, reimagined for interview coaching.

## What It Does

1. **You join a voice channel** with the practice role assigned
2. **STARCoach joins** and asks behavioral interview questions ("Tell me about a time when...")
3. **You answer** naturally — the bot listens, transcribes, and coaches you in real-time
4. **Real-time coaching** — if you're missing a STAR component (Situation, Task, Action, Result), the coach nudges you to fill it in
5. **After the session** — you get a detailed coaching report with scores, tips, and example improvements

## The STAR Method

| Component | What It Means | Example |
|-----------|--------------|---------|
| **S**ituation | Set the scene — context, background | "At my previous job, our team of 5 was behind on a critical deadline..." |
| **T**ask | Your specific role/responsibility | "I was responsible for the frontend integration..." |
| **A**ction | The concrete steps YOU took | "I set up daily standups, broke the work into sprints, and..." |
| **R**esult | The outcome + what you learned | "We delivered 2 days early, and I learned that..." |

## Quick Start

```bash
# 1. Clone and enter directory
git clone https://github.com/youruser/STARCoach.git
cd STARCoach

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up config
cp .env.example .env
# Edit .env with your tokens/keys

# 4. Customize your practice focus (optional)
# Edit interview-config.md

# 5. Run
python bot.py
```

### Prerequisites

- Python 3.10+
- FFmpeg installed ([download](https://ffmpeg.org/download.html))
- Discord bot token ([Discord Developer Portal](https://discord.com/developers))
- Deepgram API key ([console.deepgram.com](https://console.deepgram.com))
- OpenRouter API key ([openrouter.ai/keys](https://openrouter.ai/keys))

## Discord Setup

1. Create a bot in the [Discord Developer Portal](https://discord.com/developers)
2. Enable these intents: **Message Content**, **Server Members**, **Voice States**
3. Invite with permissions: Connect, Speak, Use Voice Activity, Send Messages, Embed Links
4. Create a role called `Practice` (or whatever you set in `.env`)
5. Set up a channel for coaching reports and put its ID in `REPORT_CHANNEL_ID`

## Commands

| Command | Permission | Description |
|---------|-----------|-------------|
| `!testvoice` | Everyone | Check if voice cog is loaded and working |
| `!sessions` | Manage Channels | List active practice sessions |
| `!endpractice` | Manage Channels | Manually end a practice session |
| `!history [count]` | Manage Server | View recent practice session history |
| `!session <id>` | Manage Server | View details of a specific session |
| `!transcript <id>` | Manage Server | Get full transcript of a session |
| `!reanalyze <id>` | Administrator | Re-run coaching analysis on a past session |
| `!status` | Everyone | Bot status and statistics |
| `!setrole <name>` | Administrator | Change the practice trigger role |
| `!setthreshold <n>` | Administrator | Set readiness score threshold |

## Coaching Report

After each practice session, STARCoach posts a detailed coaching report including:

- **📊 Interview Readiness Score** (0-100)
- **⭐ STAR Component Scores** — Situation Clarity, Task Definition, Action Detail, Result Impact, Overall Structure, Storytelling
- **📝 Answer-by-Answer Breakdown** — Which STAR components were present/missing per question
- **💪 What You Did Well** — Your strengths
- **🔧 Areas to Improve** — What to focus on
- **💡 Coaching Tips** — Specific, actionable advice
- **🔄 Example Improvement** — How to restructure your weakest answer
- **🎯 Overall Feedback + Next Steps**

## Customization

Edit `interview-config.md` to customize:

- Your name (for personalized coaching)
- Target role/industry
- Focus areas for behavioral questions
- Known weaknesses to watch for
- Special coaching instructions

## Tech Stack

- **Python + py-cord** — Discord bot framework with voice support
- **OpenRouter** — Claude Haiku 4.5:nitro (real-time coaching), Claude Sonnet 4.5 (analysis)
- **Deepgram** — Speech-to-text transcription
- **edge-tts** — Text-to-speech (Jenny Neural voice)
- **SQLite** — Practice session history

## Project Structure

```
bot.py                    # Entry point — STARCoach class
src/cogs/
  ├── voice.py            # STAR interview coach — LLM responses, TTS, recording
  └── admin.py            # Admin commands (!history, !reanalyze, !status)
src/services/
  ├── transcription.py    # Deepgram REST API for speech-to-text
  ├── analysis.py         # STAR coaching analysis via OpenRouter
  ├── tts.py              # Edge-TTS for text-to-speech
  └── database.py         # Async SQLite with aiosqlite
src/utils/
  └── embeds.py           # Discord embed builders for coaching reports
interview-config.md       # Customize practice focus areas
```

## License

MIT with Attribution Clause — see StaffLens LICENSE.
Forked from StaffLens by Chad Keith.

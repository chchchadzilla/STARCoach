<p align="center">
  <h1 align="center">�️ STARCoach</h1>
  <p align="center"><strong>AI-Powered STAR Interview Practice Bot for Discord</strong></p>
  <p align="center">
    <a href="#features">Features</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#commands">Commands</a> •
    <a href="#customization">Customization</a> •
    <a href="#troubleshooting">Troubleshooting</a>
  </p>
</p>

---

## What is STARCoach?

**STARCoach** is a free, open-source Discord bot that conducts live voice-based behavioral interview practice sessions using the **STAR method** (Situation, Task, Action, Result). It listens to you speak in a Discord voice channel, responds with realistic follow-up questions in real time using text-to-speech, and — when the session ends — generates a detailed coaching report grading each of your answers on STAR structure, clarity, and depth.

Think of it as a personal interview coach that's available 24/7 in your Discord server.

### ✨ Features

- 🎤 **Live Voice Interviews** — Join a voice channel, and STARCoach asks you behavioral questions out loud and listens to your answers in real time. No typing required.
- 🧠 **AI-Powered Conversation** — Powered by Claude (via OpenRouter), the bot asks contextual follow-up questions, probes for details, and keeps the conversation natural.
- 📝 **Real-Time Transcription** — Your speech is transcribed on-the-fly using Deepgram Nova-2, so you can review exactly what was said.
- 🗣️ **Text-to-Speech Responses** — The bot speaks its questions and feedback aloud using natural-sounding TTS (Microsoft Edge TTS).
- 📊 **Detailed Coaching Reports** — After each session, STARCoach analyzes your entire interview and posts a rich embed report covering:
  - Per-answer STAR breakdown (Situation / Task / Action / Result)
  - Strengths and areas for improvement
  - An overall **Readiness Score** (0–100)
  - Specific, actionable coaching tips
- 🎯 **Customizable Focus Areas** — Edit a simple config file to target specific roles, focus areas, and coaching styles.
- 📂 **Session History** — All sessions are saved to a local SQLite database. Review past transcripts, re-analyze old sessions, and track improvement over time.
- 🔒 **Self-Hosted & Private** — Runs entirely on your own machine. Your data never leaves your control.

---

## Quick Start

> **Total setup time: ~15 minutes** if you already have Python installed.

### Prerequisites

You need the following installed on your machine **before** you begin:

| Requirement | Version | How to Check | Install Link |
|---|---|---|---|
| **Python** | 3.10+ | `python --version` | [python.org/downloads](https://www.python.org/downloads/) |
| **FFmpeg** | Any recent | `ffmpeg -version` | See below |
| **Git** | Any recent | `git --version` | [git-scm.com](https://git-scm.com/) |

#### Installing FFmpeg

FFmpeg is required for voice audio processing. The bot will **not work** without it.

<details>
<summary><strong>🪟 Windows</strong></summary>

**Option A — winget (recommended):**
```bash
winget install FFmpeg
```

**Option B — Manual install:**
1. Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) (click "Windows builds" → gyan.dev or BtbN)
2. Extract the ZIP to a folder like `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your system **PATH**:
   - Search "Environment Variables" in Start Menu
   - Under "System variables", find `Path`, click Edit
   - Add `C:\ffmpeg\bin`
   - Click OK, close all windows
4. Open a **new** terminal and verify: `ffmpeg -version`

</details>

<details>
<summary><strong>🍎 macOS</strong></summary>

```bash
brew install ffmpeg
```

If you don't have Homebrew: [brew.sh](https://brew.sh/)

</details>

<details>
<summary><strong>🐧 Linux (Debian/Ubuntu)</strong></summary>

```bash
sudo apt update && sudo apt install ffmpeg
```

</details>

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/chchchadzilla/STARCoach.git
cd STARCoach
```

### Step 2 — Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

- **Windows (cmd):** `venv\Scripts\activate`
- **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source venv/bin/activate`

You should see `(venv)` at the beginning of your terminal prompt.

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** → Name it whatever you want (e.g., "STARCoach") → Create
3. Go to the **Bot** tab on the left sidebar
4. Click **"Reset Token"** → Copy the token (you'll need this in Step 5)
5. Scroll down and enable these **Privileged Gateway Intents**:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
6. Go to the **OAuth2** tab on the left sidebar
7. Under **OAuth2 URL Generator**:
   - Scopes: check `bot`
   - Bot Permissions: check these:
     - `Send Messages`
     - `Embed Links`
     - `Connect` (voice)
     - `Speak` (voice)
     - `Use Voice Activity`
8. Copy the generated URL at the bottom and open it in your browser to invite the bot to your server

### Step 5 — Configure Environment Variables

```bash
cp .env.example .env
```

> **Windows (cmd):** `copy .env.example .env`

Open `.env` in any text editor and fill in your values:

```env
# REQUIRED — paste your Discord bot token from Step 4
DISCORD_TOKEN=your_discord_bot_token_here

# REQUIRED — right-click a text channel in Discord → "Copy Channel ID"
# (You need Developer Mode on: User Settings → Advanced → Developer Mode)
REPORT_CHANNEL_ID=1234567890123456789

# REQUIRED — sign up at https://console.deepgram.com (free tier available)
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# REQUIRED — sign up at https://openrouter.ai/keys (pay-as-you-go)
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

The rest of the `.env` values have sensible defaults. See `.env.example` for all options.

#### Getting Your API Keys

<details>
<summary><strong>Deepgram API Key (for speech-to-text)</strong></summary>

1. Go to [console.deepgram.com](https://console.deepgram.com)
2. Sign up for a free account (includes $200 in free credits)
3. Go to **API Keys** in the left sidebar
4. Click **Create a New API Key**
5. Copy the key and paste it into your `.env` as `DEEPGRAM_API_KEY`

</details>

<details>
<summary><strong>OpenRouter API Key (for AI conversation & analysis)</strong></summary>

1. Go to [openrouter.ai](https://openrouter.ai)
2. Sign up / log in
3. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
4. Click **Create Key**
5. Copy the key and paste it into your `.env` as `OPENROUTER_API_KEY`
6. Add credits at [openrouter.ai/credits](https://openrouter.ai/credits) (pay-as-you-go, typically pennies per session)

</details>

### Step 6 — Create the Practice Role in Discord

1. In your Discord server, go to **Server Settings → Roles**
2. Create a new role called **`Practice`** (or whatever you set `PRACTICE_ROLE_NAME` to in `.env`)
3. Assign this role to anyone who wants to practice

> **How it works:** When a user with the Practice role joins a voice channel where the bot is present, STARCoach automatically starts a practice session. When they leave the channel, the session ends and a coaching report is generated.

### Step 7 — Run the Bot

```bash
python bot.py
```

You should see output like:

```
2025-01-01 12:00:00 | INFO     | starcoach | Loaded cog: src.cogs.voice
2025-01-01 12:00:00 | INFO     | starcoach | Loaded cog: src.cogs.admin
2025-01-01 12:00:00 | INFO     | starcoach | Logged in as STARCoach#1234 (ID: ...)
2025-01-01 12:00:00 | INFO     | starcoach | Connected to 1 guild(s)
```

🎉 **You're done!** Assign yourself the Practice role, join a voice channel, and start practicing.

---

## How a Session Works

1. **Join a voice channel** — The bot must already be in the channel (or it joins when you do, if configured). Make sure you have the Practice role.
2. **The bot greets you** — It introduces itself and asks the first behavioral question out loud.
3. **Speak your answer** — Talk naturally. The bot transcribes your speech in real time.
4. **Follow-up questions** — The bot asks clarifying questions, probes for STAR details, and keeps the conversation going.
5. **Leave the channel** — When you disconnect, the session ends automatically.
6. **Coaching report** — Within seconds, a detailed coaching report embed is posted to your configured report channel.

---

## Commands

All commands use the `!` prefix by default (configurable via `COMMAND_PREFIX` in `.env`).

### Practice Commands

| Command | Description |
|---|---|
| `!endpractice` | Manually end your current practice session (instead of leaving the voice channel) |
| `!sessions` | List all active practice sessions in the server |
| `!testvoice` | Test TTS playback in your current voice channel |

### History & Review Commands

| Command | Description |
|---|---|
| `!history [@user]` | Show recent practice sessions for yourself or another user |
| `!session <id>` | View the full coaching report for a specific session |
| `!transcript <id>` | View the raw transcript for a specific session |
| `!reanalyze <id>` | Re-run the AI analysis on a past session (useful if you change models) |

### Admin Commands

| Command | Description |
|---|---|
| `!setrole <role_name>` | Change which role triggers practice sessions |
| `!setthreshold <0-100>` | Set the readiness score threshold |
| `!status` | Show bot configuration and status |

---

## Customization

### Interview Focus & Coaching Style

Edit **`interview-config.md`** in the project root to customize:

- **Practitioner Name** — Your name (used in the coaching conversation)
- **Target Role** — The job you're preparing for
- **Focus Areas** — Specific topics the interviewer should focus on
- **Known Weaknesses** — Areas where you need extra practice
- **Special Instructions** — Adjust the coaching style (e.g., "be more aggressive with follow-ups")

The bot reads this file at the start of every session, so changes take effect immediately — no restart needed.

### AI Models

You can change the AI models in your `.env`:

```env
# Fast model for real-time conversation (needs to be quick)
OPENROUTER_MODEL=anthropic/claude-haiku-4.5:nitro

# Deeper model for post-session analysis (can be slower, higher quality)
ANALYSIS_MODEL=anthropic/claude-sonnet-4.5
```

Browse available models at [openrouter.ai/models](https://openrouter.ai/models). The `:nitro` suffix on the interview model routes to faster infrastructure — recommended for real-time voice conversations.

### Other Settings

| `.env` Variable | Default | Description |
|---|---|---|
| `PRACTICE_ROLE_NAME` | `Practice` | Discord role name that triggers sessions |
| `READINESS_THRESHOLD` | `70` | Score (0–100) to be considered "Interview Ready" |
| `COMMAND_PREFIX` | `!` | Bot command prefix |
| `DATABASE_PATH` | `data/starcoach.db` | SQLite database location |

---

## Project Structure

```
STARCoach/
├── bot.py                      # Main entry point
├── interview-config.md         # Customize interview focus & style
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── LICENSE                     # MIT License
│
├── src/
│   ├── cogs/
│   │   ├── voice.py            # Voice channel handling, live interview loop
│   │   └── admin.py            # Admin & history commands
│   │
│   ├── services/
│   │   ├── analysis.py         # Post-session STAR analysis (LLM)
│   │   ├── database.py         # SQLite database operations
│   │   ├── transcription.py    # Deepgram speech-to-text
│   │   └── tts.py              # Text-to-speech (edge-tts)
│   │
│   └── utils/
│       └── embeds.py           # Discord embed formatting for reports
│
└── data/
    └── starcoach.db            # SQLite database (auto-created)
```

---

## Troubleshooting

### Bot starts but doesn't respond to voice

- ✅ Make sure you have the **Practice** role (or whatever `PRACTICE_ROLE_NAME` is set to)
- ✅ Make sure the bot has **Connect** and **Speak** permissions in the voice channel
- ✅ Make sure `ffmpeg` is installed and on your PATH: `ffmpeg -version`
- ✅ Check the terminal for error messages

### "DISCORD_TOKEN not found"

You forgot to create the `.env` file. Run:
```bash
cp .env.example .env
```
Then fill in your values.

### OpenRouter 401 error / "User not found"

Your OpenRouter API key is invalid or expired.
1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Generate a new key
3. Update `OPENROUTER_API_KEY` in your `.env`
4. Restart the bot

### No coaching report appears after a session

- ✅ Make sure `REPORT_CHANNEL_ID` in `.env` is set to the correct channel ID
- ✅ Make sure the bot has **Send Messages** and **Embed Links** permissions in that channel
- ✅ The session needs at least a few exchanges before a report is generated

### "Chunk too big" error in logs

This is handled automatically in the current version. If you see it, make sure you're on the latest code (`git pull`).

### Bot can hear me but I can't hear the bot

- ✅ Make sure FFmpeg is installed: `ffmpeg -version`
- ✅ Try `!testvoice` to test TTS playback
- ✅ Check your Discord voice settings (output device, volume)

### Database errors

The database is auto-created on first run. If it gets corrupted:
```bash
del data\starcoach.db
```
(or `rm data/starcoach.db` on Mac/Linux), then restart the bot. Session history will be lost.

---

## Tech Stack

| Component | Technology |
|---|---|
| Bot Framework | [Py-cord](https://docs.pycord.dev/) 2.7.0 |
| Speech-to-Text | [Deepgram](https://deepgram.com/) Nova-2 |
| AI (Conversation) | [Claude Haiku 4.5](https://openrouter.ai/) via OpenRouter |
| AI (Analysis) | [Claude Sonnet 4.5](https://openrouter.ai/) via OpenRouter |
| Text-to-Speech | [edge-tts](https://github.com/rany2/edge-tts) (Microsoft Edge TTS) |
| Database | SQLite via [aiosqlite](https://github.com/omnilib/aiosqlite) |
| Audio Processing | [FFmpeg](https://ffmpeg.org/) |

---

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

**Built by [Chad Keith](https://github.com/chchchadzilla)**

## Usage

Describe the most common 1-3 workflows here with concrete commands/examples.

### Example

```bash
# Example command
```

## Demo

Add one of the following for conversion:
- GIF
- screenshot
- short video link

Even a rough GIF is better than none.

---

## Support

If this project helps you, consider:
- ⭐ starring the repo
- sharing it with someone who needs it
- supporting ongoing work: **https://buymeacoffee.com/chadpkeith**

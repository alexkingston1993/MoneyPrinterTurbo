# Session Summary — Investing, Not Trading Content Pipeline

## Channel Identity
- **Channel name**: The Compounder (English) / The Compounder Tamil / The Compounder Hindi
- **Persona**: Alex from Chennai — retail investor sharing personal views, NOT an expert
- **Core message**: "Investing, Not Trading" — 90%+ traders lose money, long-term investing builds wealth
- **Target**: Indian retail investors, spoon-fed educational content, hook-driven shorts

## SEBI Compliance
- **Safe**: "I would buy" + "do your own research" = personal opinion
- **Forbidden**: "You should buy", price targets, guaranteed returns, stock tips
- **90+ day rule**: All data must be 90+ days old, no live prices
- **Compliance module**: `app/services/compliance.py` — validates scripts against 21 banned phrases, 3 required disclaimers, price target detection

## Tech Stack & Architecture

### Installed Dependencies
- Python 3.11.15 (venv), macOS
- Coqui TTS 0.22.0 (XTTS v2 for voice cloning on CPU)
- transformers 4.37.2 (downgraded for BeamSearchScorer compat)
- torch 2.2.2 (max available for macOS x86_64 + Python 3.11)
- numpy <2 (downgraded for TTS compat)
- yfinance, mplfinance (stock data + charts)
- matplotlib 3.11.0 (chart generation)
- google-auth, google-api-python-client (YouTube upload)
- edge_tts (multilingual TTS fallback)
- moviepy (video compositing)

### Voice Pipeline (`app/services/voice.py`)
| Provider | Format | Status |
|---|---|---|
| coqui | `coqui:ref_file:lang` | ✅ Working — Alex's cloned voice (English + Hindi) |
| edge | `edge:voice_name` | ✅ Working — Tamil fallback (PallaviNeural) |
| fishspeech | `fishspeech:ref_id:lang` | Built but not tested (needs API key) |
| gemini | `gemini:voice_name` | Built but deprecated in favor of coqui |

- `COQUI_TOS_AGREED=1` env var set in code to auto-accept CPML license
- Voice reference: `app/services/voices/alex_ref.wav` (117s, 22050Hz mono WAV from user's recording)
- Per-language voice config in `config.toml`:
  - `voice_en = "coqui:app/services/voices/alex_ref.wav:en"`
  - `voice_hi = "coqui:app/services/voices/alex_ref.wav:hi"`
  - `voice_ta = "edge:ta-IN-PallaviNeural"`

### Video Resolution
- Shorts/Reels: 4K (2160×3840 portrait)
- Long-form: 8K (7680×4320 landscape)
- Frame rate: 30fps (universal)

### Content Generation Pipeline (`app/services/task.py`)
1. Generate script (English, SEBI-compliant, hook-driven)
2. Compliance validation (logs violations, blocks in strict mode)
3. Generate search terms
4. Generate audio (auto-selects voice per language)
5. Generate subtitles
6. Download video materials
7. Generate final video
8. ⭐ Multi-language: translate → audio → subtitle → video for each target language
9. Cross-post to TikTok/Instagram
10. ⭐ Upload to YouTube (if configured)

### Multi-Language Pipeline (`app/services/multilang.py`)
- Translates English script to Tamil + Hindi via LLM
- Preserves financial terms, disclaimers, and names in English
- Generates per-language audio, subtitles, and video
- Uses same video materials for all languages
- Output: `final_en.mp4`, `final_ta.mp4`, `final_hi.mp4`

### Chart Generation (`app/services/chart.py`)
| Function | Purpose |
|---|---|
| `price_trend(ticker)` | Historical stock line chart |
| `sip_growth(amount, years, rate)` | SIP compounding visualization |
| `trading_vs_investing()` | 90% traders lose vs 10% investors win |
| `sector_comparison(sectors)` | Sector performance bar chart |
| `index_comparison(tickers)` | Nifty/Sensex normalized comparison |
| `pe_band(ticker)` | PE ratio with upper/lower bands |

All return `moviepy.ImageClip` objects for compositing. Dark theme, educational disclaimers on each chart.

### Hermes News Agent (`app/services/hermes_agent.py`)
Inspired by Nous Research's Hermes Agent — self-improving news monitor.

| Component | Purpose |
|---|---|
| `KnowledgeBase` | SQLite persistent store (topics, news, queue, skills, feedback) |
| `NewsFetcher` | RSS feeds (ET, Moneycontrol, LiveMint) + GDELT project |
| `AgentBrain` | LLM-powered relevance scoring & content suggestion |
| `HermesAgent` | Orchestrator: `cycle()` = fetch → analyze → suggest → learn |

**Self-improvement loop**: Records engagement feedback → updates topic scores → creates skills from high/low performers. Skills stored as reusable patterns (e.g., "stat_shock hook works on FII outflow topics").

Agent stores in `data/hermes_agent.db`. Run `get_agent().cycle()` to fetch news and queue content.

### YouTube Upload (`app/services/youtube_uploader.py`)
- OAuth 2.0 with token persistence + auto-refresh
- 3 channels: The Compounder / The Compounder Tamil / The Compounder Hindi
- Resumable upload with progress logging
- Auto-generates compliant descriptions with disclaimer
- Supports Shorts + long-form tag sets
- Optional thumbnail upload
- 2s delay between channel uploads to avoid quota

**Setup**: Place `client_secrets_en.json` (same file for all 3) in `data/youtube_tokens/`, then run `auth_setup()` for each language.

### Config (`config.toml`)
Key settings in `[ui]` section:
- `youtube_enabled`, `youtube_auto_upload`, `youtube_privacy`
- `voice_en`, `voice_ta`, `voice_hi`
- `shorts_resolution`, `longform_resolution`, `frame_rate`
- `content_language` (default: "en")

## Files Created/Modified

### New Files
- `app/services/compliance.py` — SEBI compliance validation
- `app/services/chart.py` — Financial chart generation
- `app/services/multilang.py` — Multi-language content pipeline
- `app/services/hermes_agent.py` — Self-improving news agent
- `app/services/youtube_uploader.py` — YouTube upload automation
- `app/services/voices/alex_ref.wav` — Alex's voice reference recording

### Modified Files
- `app/services/llm.py` — Added `translate_script()`, SEBI-compliant script generation
- `app/services/task.py` — Wired compliance, multi-language, YouTube upload
- `app/services/voice.py` — Added coqui/fishspeech/edge providers, per-language voice selection
- `app/models/schema.py` — Added `target_languages`, `video_resolution`, `compliance_strict`
- `app/services/video.py` — Resolution-aware video generation (4K/8K)
- `app/config/config.py` — fishspeech config loading
- `config.toml` — Added YouTube, voice, resolution configs

### Data Directory
- `data/hermes_agent.db` — Agent knowledge base (SQLite)
- `data/youtube_tokens/` — OAuth tokens per channel
- `data/content_queue.json` — Content suggestion queue

## Conversation History (Current Session)
- **Environment Setup**: Installed `opencode` CLI and `bun` as prerequisites for VS Code extension development.
- **Audio Organization**: Created a `my audio` folder and moved two user-uploaded voice recordings (`recording.webm`, `recording_2.webm`) into it.
- **YouTube API & GCP Setup**: 
  - Advised the user to use "No organisation" when creating the GCP project.
  - Resolved a channel naming issue ("The Compounder" was rejected by YouTube; suggested alternatives like "The Compounder AK").
  - Guided the user through renaming the OAuth client JSON to `client_secrets_en.json` in the `data/youtube_tokens` directory.
  - Ran the Python OAuth setup script for the English YouTube channel and instructed the user to complete the browser-based authorization flow.

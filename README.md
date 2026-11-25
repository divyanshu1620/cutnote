# CutNote

Frame-accurate video review, timestamped voice notes, and NLE timeline export for video editors and creative agencies.

Built by **Divyanshu Malik**.

## Overview

CutNote eliminates scattered WhatsApp voice notes and vague email feedback. Editors upload a cut, generate a secure expiring review link, and clients leave frame-accurate text or voice feedback—with automatic Hindi/English transcription and one-click export to Adobe Premiere Pro and DaVinci Resolve.

## Key Features

- **Frame-Accurate Review Player:** Scrub timelines, click markers to jump directly to exact timestamps, and review cuts without requiring client logins.
- **Voice Notes with Auto-Transcription:** Record audio feedback directly in the browser, play it inline, and auto-transcribe Hindi/English speech via Groq Whisper (`whisper-large-v3-turbo`).
- **Feedback Management:** Editors can mark tasks as Done, and reviewers can delete unwanted comments or voice notes in real time.
- **NLE Timeline Export:** Export timestamped feedback directly into **Premiere Pro CSV** and **DaVinci Resolve EDL** marker formats.
- **Security-First Backend:** Cryptographically signed expiring review links (HMAC), magic-byte media validation, rate limiting, and chunked video uploads.

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy (Async), SQLite, Pydantic, httpx, Groq Whisper API
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Lucide Icons

## Local Setup

### 1. Backend
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
@'
# CutNote

Frame-accurate video review, timestamped voice notes, and NLE timeline export for video editors and creative agencies.

Built by **Divyanshu Malik**.

## Key Features
- **Frame-Accurate Review Player:** Scrub timelines, click markers to jump to exact timestamps, and review cuts without client logins.
- **Voice Notes with Auto-Transcription:** Record audio feedback in the browser, play it inline, and auto-transcribe Hindi/English speech via Groq Whisper.
- **Feedback Management:** Mark tasks as Done and delete unwanted comments or voice notes in real time.
- **NLE Timeline Export:** Export timestamped feedback to **Premiere Pro CSV** and **DaVinci Resolve EDL**.

## Tech Stack
- **Backend:** Python, FastAPI, SQLAlchemy (Async), SQLite, Groq Whisper API
- **Frontend:** React, TypeScript, Vite, Tailwind CSS

## License
Copyright (c) 2026 Divyanshu Malik. Licensed for personal, educational, and non-commercial use with attribution. Commercial resale without permission is prohibited.

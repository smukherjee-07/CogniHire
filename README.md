<div align="center">

# 🚀 COGNIHIRE

**AI-Powered Mock Interview & Candidate Evaluation Platform**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Web-lightgrey)]()

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Tech Stack](#️-tech-stack)
- [Requirements](#-requirements)
- [Installation](#-installation)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Set Up the Backend](#2-set-up-the-backend)
  - [3. Open the App](#3-open-the-app)
- [Usage](#️-usage)
- [Project Structure](#️-project-structure)
- [Troubleshooting](#️-troubleshooting)
- [Team 90](#-team-90)
- [License](#-license)

---

## 📖 Overview

CogniHire is an intelligent mock interview platform designed to bridge the gap in interview preparation by simulating realistic scenarios. It gives candidates instant, objective feedback on technical accuracy, communication skills, and professional presence using an interactive AI avatar and real-time audio/visual analysis.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🤖 **AI Interviewer Avatar** | A responsive avatar that dynamically speaks questions and listens to responses to simulate real human interaction. |
| 👔 **Professional Presence Scanner** | Vision AI integration that assesses candidate attire based on their target job role. |
| 🎙️ **Real-Time Audio Visualizers & Transcripts** | Live speech-to-text processing ensuring precise AI evaluation. |
| 📊 **Comprehensive Report Card** | An "all-at-the-end" dashboard featuring radar charts, technical scoring, and AI-suggested answers. |
| 🎨 **Dynamic Theming** | The UI automatically adapts its color palette based on the selected career path (e.g., Finance, Technical, Government). |
| 🎯 **Focus Mode** | A distraction-free live interview interface mimicking enterprise video conferencing. |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript, WebRTC |
| **Backend** | FastAPI (Python) |
| **AI & NLP** | Google Gemini API |
| **Database** | SQLite |

---

## 📋 Requirements

| Tool | Purpose |
|---|---|
| [Python 3.10+](https://www.python.org/downloads/) | Runs the backend server |
| Modern Browser (Chrome/Edge) | Webcam & microphone permissions required |
| [Git](https://git-scm.com/) | Clones the repository |

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/cognihire.git
cd cognihire
```

### 2. Set Up the Backend

<details>
<summary><strong>Windows</strong></summary>

```powershell
py -m pip install -r requirements.txt
copy .env.example .env
py app.py
```
</details>

<details>
<summary><strong>Linux / macOS</strong></summary>

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env
python3 app.py
```
</details>

> ⚠️ Copy `.env.example` to `.env` and put your Gemini API key in `GEMINI_API_KEY`. Without a key the app still runs: questions come from the built-in question bank and answers get simple local scoring. If both `GEMINI_API_KEY` and the legacy `AI_API_KEY` are set, `GEMINI_API_KEY` takes precedence.

### 3. Open the App

The backend also serves the frontend, so there is nothing else to start. Open `http://127.0.0.1:8000` in Chrome or Edge.
Check `http://127.0.0.1:8000/api/health` to confirm the server is up and whether the AI key was picked up (`ai_configured`). API reference: [docs/api.md](docs/api.md).

---

## ▶️ Usage

| Step | Action |
|---|---|
| 1 | Start the backend server (see [Set Up the Backend](#2-set-up-the-backend)); it also serves the web app |
| 2 | Open `http://127.0.0.1:8000` and log in |
| 3 | Select your target career path and enter the mock interview |
| 4 | Review your AI-generated report card once the session ends |

Run the tests with `python -m pytest -q` (the HTTP tests need `pip install -r requirements.txt`).

---

## 📂 Project File Structure

```text
CogniHire/
│
├── ai/                     # AI models and prompt engineering
│   ├── __init__.py
│   ├── api.py
│   ├── evaluator.py
│   ├── presence.py         # Attire and professional presence assessment
│   ├── prompts.py
│   └── question_generator.py
│
├── backend/                # Core API and business logic
│   ├── __init__.py
│   ├── auth.py             # Authentication and security routing
│   ├── interview.py
│   ├── question_bank.py    # Pre-defined and dynamic question logic
│   └── session.py
│
├── data/                   # Dynamic media storage
│   ├── audio/              # Temporary audio capture storage
│   │   └── .gitkeep
│   ├── video/              # Temporary video snapshot storage
│   │   └── .gitkeep
│   └── .gitkeep
│
├── database/               # Database schemas and operations
│   ├── answers.sql         # SQL queries for tracking candidate answers
│   ├── cognihire.db        # Active SQLite database
│   ├── database.py
│   ├── queries.sql         # Auth and session queries
│   ├── schema.sql
│   └── seed.sql
│
├── docs/                   
│   └── documentation/      # Project documentation files
│       ├── api.md
│       ├── architecture.md
│       ├── database.md
│       ├── project_flow.md
│       └── setup.md
│
├── speech_video/           # Media processing modules
│   ├── __init__.py
│   ├── audio.py
│   ├── speech_to_text.py
│   └── video.py
│
├── tests/                  # Unit and integration tests
│   ├── __init__.py
│   ├── test_ai.py
│   ├── test_backend.py
│   ├── test_database.py
│   ├── test_interview_flow.py
│   └── test_speech_video.py
│
├── web/                    # Frontend UI/UX directory
│
├── .env.example            # Environment variables template
├── .gitignore
├── LICENSE
├── README.md
├── app.py                  # Main application entry point
└── requirements.txt        # Python project dependencies
```

---

## 🛠️ Troubleshooting

| Issue | Likely Fix |
|---|---|
| Webcam/mic not detected | Grant browser permissions and confirm no other app is using the device. |
| AI avatar unresponsive | Check that Gemini/OpenAI API keys are set correctly in `.env`. |
| Backend fails to start | Re-run `pip install -r requirements.txt` in the correct Python environment. |
| Questions/scores look generic | Open `/api/health`: if `ai_configured` is `false`, the key is missing; if `true`, look for `AI ... failed` lines in the server log (wrong model name, quota) - the app falls back to the question bank and local scoring. |
| Blank report card | Ensure the interview session ran to completion before ending it. |

---

## 👥 Team 90

Developed for **Project Exhibition I (DSN2098)** at VIT Bhopal University.

| Role | Member | Registration No. |
|---|---|---|
| **Frontend Development** | Rudraksha Gaharwar | 25BAI10635 |
| **Frontend Development** | Ansh Tiwari | 25BAI10334 |
| **Backend Development** | Aryan Chirag | 25BAI11075 |
| **Backend Development** | Anway Basu | 25BAI11029 |
| **Database & Deployment** | Subhradip Roy | 25BAI10130 |
| **Project Planning & Integration** | Soumallaya Mukherjee | 25BAI10226 |

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

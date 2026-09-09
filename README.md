<div align="center">

# 🚀 COGNIHIRE

**AI-Powered Mock Interview & Candidate Evaluation Platform**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Flask-009688?logo=fastapi&logoColor=white)]()
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
  - [2. Launch the Frontend](#2-launch-the-frontend)
  - [3. Set Up the Backend](#3-set-up-the-backend)
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
| **Backend** | FastAPI / Flask (Python) |
| **AI & NLP** | Google Gemini API, OpenAI API |
| **Database** | SQLite / MySQL |

---

## 📋 Requirements

| Tool | Purpose |
|---|---|
| [Python 3.8+](https://www.python.org/downloads/) | Runs the backend server |
| Modern Browser (Chrome/Edge) | Webcam & microphone permissions required |
| [Git](https://git-scm.com/) | Clones the repository |

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/cognihire.git
cd cognihire
```

### 2. Launch the Frontend

<details>
<summary><strong>Windows / Linux / macOS</strong></summary>

```bash
cd web
python -m http.server 8080
```

Then open your browser and navigate to `http://localhost:8080` to view the login screen.
</details>

### 3. Set Up the Backend

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

> ⚠️ Copy `.env.example` to `.env` and fill in your Google Gemini / OpenAI API keys before starting the backend.

---

## ▶️ Usage

| Step | Action |
|---|---|
| 1 | Start the backend server (see [Set Up the Backend](#3-set-up-the-backend)) |
| 2 | Start the frontend server (see [Launch the Frontend](#2-launch-the-frontend)) |
| 3 | Open `http://localhost:8080` and log in |
| 4 | Select your target career path and enter the mock interview |
| 5 | Review your AI-generated report card once the session ends |

---

## 🗂️ Project Structure

```text
CogniHire/
│
├── ai/
│   ├── __init__.py
│   ├── api.py
│   ├── evaluator.py
│   ├── prompts.py
│   └── question_generator.py
│
├── backend/
│   ├── __init__.py
│   ├── interview.py
│   └── session.py
│
├── data/
│
├── database/
│   ├── cognihire.db
│   ├── database.py
│   ├── schema.sql
│   └── seed.sql
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── database.md
│   ├── project_flow.md
│   └── setup.md
│
├── speech_video/
│   ├── __init__.py
│   ├── audio.py
│   ├── speech_to_text.py
│   └── video.py
│
├── tests/
│   ├── __init__.py
│   ├── test_ai.py
│   ├── test_backend.py
│   ├── test_database.py
│   ├── test_interview_flow.py
│   └── test_speech_video.py
│
├── web/
│   ├── assets/
│   │
│   ├── css/
│   │   ├── components.css
│   │   ├── responsive.css
│   │   └── style.css
│   │
│   ├── js/
│   │   ├── api.js
│   │   ├── app.js
│   │   ├── dashboard.js
│   │   ├── history.js
│   │   ├── interview.js
│   │   ├── media.js
│   │   ├── results.js
│   │   └── theme.js
│   │
│   └── index.html
│
├── .env
├── .env.example
├── .gitignore
├── app.py
├── LICENSE
├── README.md
└── requirements.txt
```

---

## 🛠️ Troubleshooting

| Issue | Likely Fix |
|---|---|
| Webcam/mic not detected | Grant browser permissions and confirm no other app is using the device. |
| AI avatar unresponsive | Check that Gemini/OpenAI API keys are set correctly in `.env`. |
| Backend fails to start | Re-run `pip install -r requirements.txt` in the correct Python environment. |
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

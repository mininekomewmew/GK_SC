# Spec: Football Prediction & Analysis LINE Bot (Phase 1)

**Date**: 2026-08-04  
**Author**: Aun (Antigravity)  
**Status**: Draft (Awaiting P'Meow's Approval)

---

## 1. Goal & Scope (Phase 1)
Build a backend system in **Python 3.11** using **FastAPI** that acts as a LINE Bot webhook. The bot scrapes real-time match stats and odds from `goal7.co`, performs mathematical modeling (Poisson goal model + Dynamic Form Elo + Market Edge analysis), and responds to user queries.

This phase focuses entirely on local mathematical calculations without external AI APIs (to be added in Phase 2).

---

## 2. Architecture & File Structure
The project will be structured as follows:
```text
predic/
├── app/
│   ├── __init__.py
│   ├── main.py         # FastAPI Webhook Server & route routing
│   ├── scraper.py      # Goal7.co scraping engine (extracts JSON variables)
│   ├── model.py        # Mathematical models (Poisson + Form Elo + Edge Decoder)
│   └── line_bot.py     # LINE Bot API client & signature validator
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-08-04-football-prediction-bot-design.md  # This spec file
├── .env                # Local secrets (LINE Bot Channel Secret, Channel Access Token)
├── requirements.txt    # dependencies: fastapi, uvicorn, requests, lxml
└── AGENTS.md           # Custom agent persona guidelines (created)
```

---

## 3. Core Engine Specifications

### A. Web Scraper (`app/scraper.py`)
- **Target 1: Match Schedule (`https://goal7.co/`)**
  - Extract match IDs, team names, kicking times, handicap line, and expert prediction summaries.
- **Target 2: Match Analysis (`https://goal7.co/analyse/?id=[id]`)**
  - Scrape the page using `requests` with custom headers.
  - Use regex to extract embedded Javascript variables containing raw JSON:
    - `gameInfo`: Basic match data (handicap, teams).
    - `gameTeamHistory`: Last 20 matches of Team A and Team B (including date, goals, handicap, result).
    - `gamePrediction`: The website's expert comment (`ct`) and prediction (`p`).

### B. Mathematical Models (`app/model.py`)
1. **Dynamic Form Elo (Form Rating)**:
   - Apply exponential time-decay weight $w_i = e^{-\gamma \cdot i}$ where $i = 0$ (latest) to $19$ (oldest), and decay rate $\gamma = 0.05$.
   - Calculate Team A's recent win/draw/loss form, adjusted for the difficulty of historical opponents (based on the handicap line in historical matches).
2. **Poisson Score Engine**:
   - Compute Team A's home attack strength and Team B's away defense weakness.
   - Calculate expected goals: $xG_{home}$ and $xG_{away}$.
   - Generate exact score probability matrix (up to 5x5 goals) using the Poisson formula:
     $$P(X=k) = \frac{e^{-\lambda} \lambda^k}{k!}$$
   - Derive cumulative Win/Draw/Loss probabilities ($P_H, P_D, P_A$) and Handicap-cover probabilities.
3. **Market Edge Analysis**:
   - Parse bookmaker handicap odds from `gameInfo` probability.
   - Remove bookmaker margin via normalization: $P_{market} = \frac{P'_{option}}{\sum P'_{option}}$.
   - Compute Edge: $\text{Edge} = P_{model\_probability} - P_{market\_implied\_probability}$.
   - **"ทีเด็ด" Selection Logic (Option B)**: Matches are selected as "ทีเด็ด" (Best Tips) only if the calculated Value Edge is $\ge 5\%$ (configurable). This targets long-term mathematical profitability by exploiting bookmaker mispricings, aiming for a consistent hit rate above the $\approx 52.6\%$ break-even threshold.


### C. LINE Bot Webhook (`app/main.py` & `app/line_bot.py`)
- Tunnels webhook requests from LINE Platform (can be tested locally using ngrok).
- Validates the signature header `x-line-signature` using HMAC-SHA256 with `LINE_CHANNEL_SECRET`.
- Handles commands from users:
  1. **Command 1: "ทีเด็ด" or "ทีเด็ดวันนี้"**
     - Scrape the main page for matches and display today's key matchups with handicap odds.
  2. **Command 2: "วิเคราะห์ [ชื่อทีม]" (e.g. "วิเคราะห์ มอลล์บี้")**
     - Match the name to today's schedule.
     - Scrape the analysis page.
     - Run Poisson & Edge models.
     - Respond with a beautiful text summary:
       - Match details (Teams, League, Kickoff).
       - Expected Goals (xG) & Top score probabilities.
       - Handicap Line & bookmaker odds.
       - Mathematical Edge analysis (Value recommendation).

---

## 4. Verification Plan

### Automated Tests
- Create a test script `test_prediction.py` in `app/` that loads a local HTML copy of an analysis page and asserts that the parsing, Poisson calculation, and edge calculation run successfully without crashing.

### Manual Verification
- Run FastAPI server using Uvicorn.
- Expose port 8000 using Ngrok.
- Register Webhook in LINE Developers console.
- Message the bot from a real LINE account to verify interaction.

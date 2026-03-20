# Pulse — Student Wellness Dashboard

A personalized ML-powered wellness app for students. Pulse models how sleep, stress, workload, and habits influence productivity and burnout — and recommends sustainable daily schedules based on your individual patterns.

Built by a high school sophomore as a passion project, with the goal of helping students avoid burnout and perform sustainably.

---

## What it does

**Personalized performance modeling** — a Ridge regression model trained on your own data learns which factors matter most to you specifically. Someone who is sleep-sensitive gets different recommendations than someone who is stress-resistant.

**Burnout estimation** — tracks fatigue, stress, and sleep deficit over rolling 7-day windows to estimate how close you are to burning out before it happens.

**Schedule recommendations** — a Monte Carlo optimizer simulates hundreds of possible tomorrow schedules and finds the one that maximizes performance while keeping burnout low, anchored to your personal historical baselines.

**Task tracking** — add daily tasks by category (study, training, personal), mark them complete, and watch a progress bar fill toward your recommended study goal. Tasks can carry over to the next day if incomplete.

**Log prefill from tasks** — when you log your day, study and training hours are automatically pre-filled from your completed tasks so you're not double-entering data.

**History and streaks** — view your last 14 entries in a color-coded table, track your logging streak, and see weekly completion rates.

---

## Tech stack

**Frontend** — React + Vite, no UI library, custom CSS variables with light/dark mode

**Backend** — FastAPI (Python), served with Uvicorn

**ML pipeline** — scikit-learn (Ridge regression, PolynomialFeatures, StandardScaler), NumPy, Pandas

**Auth** — JWT tokens via python-jose, bcrypt password hashing via passlib

**Storage** — CSV files per user for wellness logs, JSON files for tasks and auth

---

## Project structure

```
pulse-app/
├── backend/
│   ├── api.py                  # FastAPI routes + JWT auth middleware
│   ├── auth.py                 # Registration, login, token management
│   ├── student_data.py         # CSV loading + feature engineering
│   ├── performance_model.py    # Ridge regression model + personalization
│   ├── recommendation_engine.py # Monte Carlo schedule optimizer
│   ├── task_manager.py         # Task CRUD + carry-over logic
│   ├── requirements.txt
│   └── Procfile                # For Railway deployment
└── frontend/
    ├── src/
    │   ├── App.jsx             # Root component + theme system
    │   ├── api.js              # Centralized fetch with JWT injection
    │   ├── index.css
    │   └── components/
    │       ├── Dashboard.jsx   # Main overview with interactive chart
    │       ├── LogEntry.jsx    # Daily wellness logging
    │       ├── Tasks.jsx       # Task management + weekly stats
    │       └── UserSelect.jsx  # Login + registration
    ├── package.json
    └── vite.config.js
```

---

## Running locally

**Prerequisites** — Python 3.9+, Node.js 18+

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload
```

**Frontend** (in a separate terminal)
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` (or `http://localhost:3000` if 5173 is in use).

---

## Environment variables

Create a `.env` file in your `backend/` folder:

```
PULSE_SECRET=your-long-random-secret-key
FRONTEND_URL=https://your-frontend.vercel.app
```

For local development the defaults work fine. For production, generate a real secret key and set `FRONTEND_URL` to your deployed frontend URL.

---

## How the ML works

Each user's data is a time series of daily entries: sleep hours, study hours, training hours, stress (1-10), fatigue (1-10), and productivity (1-10).

`StudentData` computes 7-day rolling averages and a burnout risk score from these raw inputs.

`PerformanceModel` takes the rolling averages, adds polynomial interaction features (e.g. sleep × stress), and fits a Ridge regression model. The trained coefficients reveal which factors most influence *that specific user's* performance — this is the personalization.

`RecommendationEngine` runs 400 Monte Carlo simulations of possible tomorrow schedules, scores each one using the trained model plus heuristics (sleep quality curve, workload curve, situational adjustments for fatigue and stress), and returns the highest-scoring plan. A fixed random seed makes results deterministic.

---

## Planned features

- [ ] Database migration (SQLite → PostgreSQL)
- [ ] School calendar API integration for automatic assignment tracking
- [ ] Weekly email summary
- [ ] AI-powered explanations ("why is my burnout rising?")
- [ ] Onboarding flow for new users

---

## License

MIT
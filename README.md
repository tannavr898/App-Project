# Student Wellness Dashboard

A modern, interactive dashboard for tracking student wellness metrics and getting AI-powered recommendations.

## Features

✨ **Dashboard Overview**
- 📈 Real-time burnout and performance charts
- 📊 Detailed metrics visualization (sleep, stress, fatigue, productivity)
- 📋 Today's wellness stats at a glance
- 🔮 Personalized recommendations for tomorrow

📱 **Data Management**
- ➕ Easy form to log daily metrics
- 👥 Multi-user support (separate data per student)
- 📥 Download data as CSV
- 📋 View raw data in table format

🧠 **AI-Powered Intelligence**
- ML-based performance prediction
- Personalized sleep & workload optimization
- Burnout risk assessment
- Individual baseline calculation

## Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Running the Application
The project now exposes a single entry point, `main.py`, which can operate
in either a command‑line or web‑based mode.

- **CLI mode** (default):
  ```bash
  python main.py --data data/synthetic_high_stress.csv
  ```
  This prints user profile, baselines and plots using `matplotlib`.

- **Web UI mode** (Streamlit):
  ```bash
  python main.py --ui streamlit
  ```
  or equivalently:
  ```bash
  streamlit run app.py
  ```
  The second form still works because `app.py` now wraps the same UI
  logic inside a `run_streamlit_app()` function and calls it when run
  directly. It is imported by `main.py` when `--ui streamlit` is used.

The dashboard will open at `http://localhost:8501` when using Streamlit.

## How to Use

### For First-Time Users
1. Open the dashboard
2. Go to **User Management** in the sidebar
3. Select "Create New User" and enter your name
4. Click the **"➕ Add New Entry"** tab
5. Fill in today's metrics:
   - 😴 Sleep hours
   - 📚 Study hours
   - 🏋️ Training hours
   - 😰 Stress level (0-10)
   - 😵 Fatigue level (0-10)
   - 💪 Productivity rating (0-10)
6. Click **"💾 Save Entry"**

### Viewing Your Dashboard
1. Go to the **"📈 Dashboard"** tab
2. View today's metrics in the summary cards
3. Check burnout and performance trends in the charts
4. Review tomorrow's personalized recommendation

### Understanding Your Data
- **Burnout Risk**: Score from 0-100. Lower is better.
- **Performance Score**: Score from 0-100. Higher is better.
- **Personal Baselines**: Your historical optimal sleep and workload when you performed best.

## Data Storage

All user data is stored in the `users/` directory as individual CSV files:
- `users/john_smith.csv` for user "john smith"
- Each entry is automatically appended when you save new data

## Project Structure

```
├── app.py                      # Main Streamlit dashboard
├── main.py                     # Original CLI version
├── student_data.py             # Data loading & feature engineering
├── performance_model.py        # ML model for performance prediction
├── recommendation_engine.py    # Optimization for recommendations
├── requirements.txt            # Python dependencies
├── data/                       # Sample synthetic datasets
│   ├── normal.csv
│   ├── synthetic_*.csv         # Various scenario simulations
└── users/                      # User data (created automatically)
    ├── user1.csv
    └── user2.csv
```

## Understanding the Models

### Performance Model
- Trained on historical data
- Considers: sleep, stress, fatigue, workload, productivity rating
- Outputs: 0-100 performance score

### Recommendation Engine
- Uses randomized search (1500 iterations) to find optimal schedule
- Factors in:
  - Personal baselines (optimal sleep & workload)
  - Current fatigue and stress levels
  - Burnout risk prediction
  - Situational context (sleep-deprived? overloaded? etc.)
- Recommends tomorrow's: sleep hours, study hours, training hours
- Predicts: performance and burnout for that schedule

## Tips & Best Practices

📝 **Tracking Tips**
- Log your data at the same time each day for consistency
- Be honest with self-ratings (stress, fatigue, productivity)
- Use the recommendations as a guide, not absolute rules

📊 **Data Quality**
- Need at least 7 days of data for accurate trends
- More data = better personalization
- Avoid large gaps in logging

🎯 **Using Recommendations**
- Follow the suggested schedule for 2-3 days
- Monitor if it actually improves your performance
- Adjust manually if needed based on your gut feeling

## Customization

### Change the Input Form
Edit the form in the **"➕ Add New Entry"** section of `app.py`

### Modify Recommendation Weights
Edit the scoring function in `recommendation_engine.py` (look for `# ------ FINAL SCORING ------`)

### Add More Metrics
1. Update the CSV structure in `save_user_data()` function
2. Add feature engineering in `student_data.py`
3. Retrain the model

## Troubleshooting

**"No data found for [user]"**
- This is normal for new users. Add your first entry using the form.

**Model predictions seem off**
- You need at least 7 days of data for good predictions
- More data improves personalization

**Charts not showing**
- Make sure you have at least 2 data points
- Check that dates are consecutive

## Future Enhancements

🚀 Ideas for expansion:
- [ ] Mobile app version
- [ ] Integration with calendar/schedule APIs
- [ ] Social comparison (anonymized peer benchmarks)
- [ ] Email notifications for recommendations
- [ ] Habit tracking for recommendations
- [ ] Advanced analytics (correlation analysis)
- [ ] Export reports as PDF

## Support

For issues or questions, check:
1. The data format in `users/` directory
2. That all dependencies are installed: `pip list`
3. Streamlit logs: `streamlit run app.py --logger.level=debug`

---

Built with ❤️ using Streamlit, Scikit-learn, and Plotly

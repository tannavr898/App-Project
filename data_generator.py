import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_student_data(num_days=100, scenario='balanced', seed=42):
    """
    Generates synthetic student data with controlled distributions for testing.

    The generator no longer just draws every column from a single normal distribution;
    each variable has a sensible default range and many named scenarios that tweak
    one or more factors so you can easily reproduce the test cases described by the
    user (see README or function doc comment for the list).

    Parameters:
    - num_days: number of rows to produce. 7/14/30 are valid "beginner" lengths.
    - scenario: one of the predefined patterns listed below.  Defaults to 'balanced'.
    - seed: random seed for reproducibility.

    Supported scenarios:
    * balanced           – normal life (sleep ≈8h, stress/fatigue ≈5/10, load moderate)
    * low_sleep          – sleep forced to 3–5h (severe deprivation)
    * perfect_recovery   – 9–10h sleep, low stress/fatigue, moderate load
    * high_load_good_sleep – 8–9h sleep with high study & training
    * high_stress_spike  – stress spikes to 8–10, other factors normal
    * chronic_fatigue    – fatigue drifts upward over the series
    * noise_stress_test  – wildly inconsistent inputs for robustness checks
    * overloaded, high_stress, high_fatigue (legacy)

    Returns a DataFrame with columns:
    date, sleep_hours, study_hours, training_hours, stress, fatigue, productivity
    """
    np.random.seed(seed)
    start_date = datetime(2023, 1, 1)

    # initialize date index
    dates = [start_date + timedelta(days=i) for i in range(num_days)]
    data = {'date': dates}

    # default ranges (these can be modified per‑scenario below)
    sleep_base = np.random.normal(8, 1.5, num_days)
    study_base = np.random.normal(3, 1.0, num_days)
    training_base = np.random.normal(1, 0.5, num_days)
    stress_base = np.random.normal(5, 1.5, num_days)
    fatigue_base = np.random.normal(4, 1.0, num_days)

    # scenario adjustments --------------------------------------------------
    if scenario == 'low_sleep' or scenario == 'severe_sleep_deprivation':
        # 1️⃣ severe sleep deprivation
        sleep_base = np.random.uniform(3, 5, num_days)
        # stress and load remain at default ranges

    elif scenario == 'perfect_recovery':
        # 2️⃣ perfect recovery day
        sleep_base = np.random.uniform(9, 10, num_days)
        stress_base = np.random.uniform(1, 3, num_days)
        fatigue_base = np.random.uniform(1, 2, num_days)
        study_base = np.random.normal(3, 0.5, num_days)  # moderate
        training_base = np.random.normal(1, 0.2, num_days)

    elif scenario == 'high_load_good_sleep':
        # 3️⃣ high load + good sleep
        sleep_base = np.random.uniform(8, 9, num_days)
        study_base = np.random.uniform(4, 6, num_days)
        training_base = np.random.uniform(1.5, 2.5, num_days)
        stress_base = np.random.uniform(4, 6, num_days)

    elif scenario == 'high_stress_spike':
        # 4️⃣ high stress spike
        stress_base = np.random.uniform(8, 10, num_days)

    elif scenario == 'chronic_fatigue':
        # 5️⃣ chronic fatigue – fatigue drifts upward gradually
        sleep_base = np.random.normal(6.5, 0.5, num_days)
        fatigue_base = np.linspace(4, 8, num_days) + np.random.normal(0, 0.3, num_days)
        stress_base = np.random.normal(5, 1, num_days)

    elif scenario == 'noise_stress_test':
        # 7️⃣ random noise stress test – wide ranges, occasional spikes
        sleep_base = np.random.uniform(3, 12, num_days)
        study_base = np.random.uniform(0, 6, num_days)
        training_base = np.random.uniform(0, 3, num_days)
        stress_base = np.random.uniform(1, 10, num_days)
        fatigue_base = np.random.uniform(1, 10, num_days)

    # the old named cases remain for compatibility
    elif scenario == 'high_stress':
        stress_base = np.random.normal(8, 1, num_days)
    elif scenario == 'high_fatigue':
        fatigue_base = np.random.normal(7, 1, num_days)
    elif scenario == 'overloaded':
        study_base = np.random.normal(4, 1, num_days)
        training_base = np.random.normal(2, 0.5, num_days)
        stress_base = np.random.normal(7, 1, num_days)
        fatigue_base = np.random.normal(6, 1, num_days)

    # Clip to realistic ranges
    sleep_hours = np.clip(sleep_base, 4, 12).round(2)
    study_hours = np.clip(study_base, 0, 6).round(2)
    training_hours = np.clip(training_base, 0, 3).round(2)
    stress = np.clip(stress_base, 1, 10).round(2)
    fatigue = np.clip(fatigue_base, 1, 10).round(2)

    # Add correlations and noise
    # Fatigue increases with low sleep and high load
    load = study_hours + training_hours
    fatigue += 0.5 * (8 - sleep_hours) + 0.2 * load # increases if sleep is below 8 or load is high
    fatigue = np.clip(fatigue, 1, 10)

    # Stress increases with load and fatigue
    stress += 0.3 * load + 0.2 * fatigue
    stress = np.clip(stress, 1, 10)

    # Productivity calculation (1-10 scale, self-rated)
    # Higher with good sleep, study/training engagement
    # Lower with high stress and fatigue
    productivity = (
        5 +  # Base (5/10)
        0.5 * (sleep_hours - 6) +  # Sleep benefit
        0.4 * study_hours +  # Study engagement
        0.3 * training_hours +  # Training engagement
        -0.3 * (stress - 5) +  # Stress penalty
        -0.4 * (fatigue - 4)  # Fatigue penalty
    )
    productivity += np.random.normal(0, 0.5, num_days)  # Noise
    productivity = np.clip(productivity, 1, 10).round(2)  # 1-10 scale

    # Populate data
    data['sleep_hours'] = sleep_hours.round(2)
    data['study_hours'] = study_hours.round(2)
    data['training_hours'] = training_hours.round(2)
    data['stress'] = stress.round(2)
    data['fatigue'] = fatigue.round(2)
    data['productivity'] = productivity.round(2)

    df = pd.DataFrame(data)
    df['date'] = df['date'].dt.date  # Format as date
    return df

def save_datasets():
    """Generates and saves multiple datasets for testing."""
    os.makedirs('data', exist_ok=True)

    # Small dataset - balanced
    df_small = generate_student_data(30, 'balanced')
    df_small.to_csv('data/synthetic_small_balanced.csv', index=False)

    # Large dataset - balanced
    df_large = generate_student_data(365, 'balanced')
    df_large.to_csv('data/synthetic_large_balanced.csv', index=False)

    # Low sleep / deprivation
    df_low_sleep = generate_student_data(100, 'severe_sleep_deprivation')
    df_low_sleep.to_csv('data/synthetic_low_sleep.csv', index=False)

    # Perfect recovery
    df_recovery = generate_student_data(100, 'perfect_recovery')
    df_recovery.to_csv('data/synthetic_perfect_recovery.csv', index=False)

    # High load + good sleep
    df_high_load = generate_student_data(100, 'high_load_good_sleep')
    df_high_load.to_csv('data/synthetic_high_load_good_sleep.csv', index=False)

    # High stress spike
    df_stress_spike = generate_student_data(100, 'high_stress_spike')
    df_stress_spike.to_csv('data/synthetic_high_stress.csv', index=False)

    # Chronic fatigue
    df_chronic = generate_student_data(100, 'chronic_fatigue')
    df_chronic.to_csv('data/synthetic_chronic_fatigue.csv', index=False)

    # Random noise stress test
    df_noise = generate_student_data(100, 'noise_stress_test')
    df_noise.to_csv('data/synthetic_noise.csv', index=False)

    # Legacy scenarios for backward compatibility
    df_overloaded = generate_student_data(100, 'overloaded')
    df_overloaded.to_csv('data/synthetic_overloaded.csv', index=False)

    print("Datasets generated and saved in 'data/' folder.")

if __name__ == "__main__":
    save_datasets()
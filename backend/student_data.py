import pandas as pd
import numpy as np


class StudentData:
    """
    Handles:
    - Loading CSV
    -Feature Engineeringg
    -Rolling Averages that work for ANY length of data
    - Burnout Calculation
    """
    
    def __init__(self, csv_path):
        self.df = pd.read_csv(csv_path)
        self._prepare_dataframes()
        self._compute_features()
        
    # --------------------------------------------------------
    def _prepare_dataframes(self):
        self.df['date'] = pd.to_datetime(self.df['date'])
        self.df = self.df.sort_values('date').reset_index(drop=True)
        self.df = self.df.dropna().reset_index(drop=True)
        
    # --------------------------------------------------------
    def _compute_features(self):
        df = self.df
        
        # Sleep Deficit
        df['sleep_deficit'] = np.maximum(0, 8 - df['sleep_hours'])
        
        # Dynamic rolling window (KEY FIX)
        window = min(7, len(df))
        
        df['avg_sleep_7'] = df['sleep_hours'].rolling(window, min_periods=1).mean()
        df['avg_study_7'] = df['study_hours'].rolling(window, min_periods=1).mean()
        df['avg_training_7'] = df['training_hours'].rolling(window, min_periods=1).mean()
        df['avg_stress_7'] = df['stress'].rolling(window, min_periods=1).mean()
        df['avg_fatigue_7'] = df['fatigue'].rolling(window, min_periods=1).mean()
        df['avg_productivity_7'] = df['productivity'].rolling(window, min_periods=1).mean()
        
        # Workload
        df['avg_load'] = df['avg_study_7'] + df['avg_training_7']
        
        # Performancee Variability
        df['performance_variability'] = df['productivity'].rolling(window, min_periods=1).std().fillna(0)
        
        # ========= Burnout Calculation =================
        fatigue_norm = df['fatigue'] / 10
        stress_norm = df['stress'] / 10
        sleep_def_norm = df['sleep_deficit'] / 4
        
        variability_score = (
            df['performance_variability'] / 
            (df['performance_variability'].max() + 1e-6)
        )
        
        df['burnout_risk'] = (
            0.3 * fatigue_norm + 
            0.3 * stress_norm + 
            0.3 * sleep_def_norm + 
            0.1 * variability_score 
        ) * 100
        
        if len(df) > 14:
            burnout_min = df['burnout_risk'].min()
            burnout_max = df['burnout_risk'].max()
            if burnout_max - burnout_min == 0:
                df['burnout_risk'] = 50.0
            else:
                df['burnout_risk'] = (
                    (df['burnout_risk'] - burnout_min) /
                    (burnout_max - burnout_min)
                ) * 100
        
        self.df = df
        
        
    # --------------------------------------------------------
    def get_dataframe(self):
        return self.df





























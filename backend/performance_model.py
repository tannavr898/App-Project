import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.metrics import r2_score, mean_squared_error

class PerformanceModel:
    """
    Handles:
    - ML training
    - Personalization coefficients
    - Performance prediction
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.poly = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
        self.model = Ridge(alpha=1.0)
        self.trained = False

    # --------------------------------------------------
    
    def _add_performance_score(self, df):
        df = df.copy()

        df['sleep_effect'] = -8 * (df['avg_sleep_7'] - 8) ** 2 + 64
        df['workload_effect'] = -4 * (df['avg_load'] - 5) ** 2 + 80
        df['stress_effect'] = -3 * df['avg_stress_7']
        df['fatigue_effect'] = -6 * (df['avg_fatigue_7']**1.3)
        # self rating is already a rolling average computed by StudentData
        df['self_rated_productivity'] = df['avg_productivity_7']
        df['sleep_vs_stress'] = df['avg_sleep_7'] / (df['avg_stress_7'] + 1e-3)
        df['fatigue_delta'] = df['avg_fatigue_7'] - df['avg_fatigue_7'].rolling(3).mean()
        df['load_ratio'] = df['avg_load'] / (df['avg_sleep_7'] + 1e-3)
        
        # build a base score from the traditional factors
        df['base_score'] = (
            df['sleep_effect'] +
            df['workload_effect'] +
            df['stress_effect'] +
            df['fatigue_effect']
        )
        
        # resilience factor: if the user rates productivity above their personal mean
        # we down–weight the penalties from the other effects. the divisor 10 keeps
        # the adjustment within a reasonable range.
        prod_mean = df['self_rated_productivity'].mean()
        df['resilience_factor'] = 1 + (df['self_rated_productivity'] - prod_mean) / 10.0
        
        # final performance score combines scaled base score and the raw self rating
        df['performance_score'] = df['base_score'] * df['resilience_factor'] + df['self_rated_productivity']
        
        # normalise to 0–100 so downstream code can treat it like a percentage
        if len(df) > 14:
            perf_min = df['performance_score'].min()
            perf_max = df['performance_score'].max()
            if perf_max - perf_min == 0:
                df['performance_score'] = 50.0
            else:
                df['performance_score'] = (
                    (df['performance_score'] - perf_min) /
                    (perf_max - perf_min)
                ) * 100

        return df
    
    
    def train(self, df):
        if df.empty:
            print("No data to train on.")
            return
        df = self._add_performance_score(df)
        df = df.dropna().reset_index(drop=True)
        if df.empty:
            print("No valid data after cleaning.")
            return

        # include the self‑rated productivity as a feature so the model can learn
        # personal "resilience" patterns (productive despite adversity)
        X = df[['avg_sleep_7', 'avg_stress_7', 'avg_fatigue_7', 'avg_load', 'self_rated_productivity']]
        y = df['performance_score']  # still using the engineered score as the target

        X_scaled = self.scaler.fit_transform(X)
        X_poly = self.poly.fit_transform(X_scaled)

        if len(X_poly) < 2:
            print("Not enough data for training (need at least 2 samples).")
            return

        split_idx = int(len(X_poly) * 0.8)

        X_train = X_poly[:split_idx]
        X_test = X_poly[split_idx:]
        y_train = y[:split_idx]
        y_test = y[split_idx:]
        
        print("Train Size: ", len(X_train))
        print("Test Size: ", len(X_test))

        self.model.fit(X_train, y_train)

        if len(X_test) > 0:
            y_pred = self.model.predict(X_test)
            print("R2 Score:", r2_score(y_test, y_pred))
            print("MSE:", mean_squared_error(y_test, y_pred))
            
        print("=== DEBUG ===")
        print("Rows:", len(df))
        print("Train:", len(X_train), "Test:", len(X_test))
        print("Features:", X_train.shape[1])
        print("Columns:", list(X.columns))
        print("Performance range:",
            y.min(), y.max())

        self.trained = True

    # --------------------------------------------------
    def predict(self, features_dict):
        if not self.trained:
            raise ValueError("Model not trained yet.")

        # expect caller to pass the current self rating along with the other
        # rolling averages; it defaults to the latest known value in the
        # recommendation engine if none is provided.
        # if the caller passed the rolling productivity average rather than
        # the renamed feature, copy it over to match the column list used in
        # training.
        if 'self_rated_productivity' not in features_dict and 'avg_productivity_7' in features_dict:
            features_dict['self_rated_productivity'] = features_dict['avg_productivity_7']

        X = pd.DataFrame([features_dict])[ 
            ['avg_sleep_7', 'avg_stress_7', 'avg_fatigue_7', 'avg_load', 'self_rated_productivity']
        ]
    
        X_scaled = self.scaler.transform(X)
        X_poly = self.poly.transform(X_scaled)
        pred = float(self.model.predict(X_poly)[0])
        
        # Clip to realistic 0-100
        pred_clipped = np.clip(pred, 0, 100)
        
        return pred_clipped

    # --------------------------------------------------
    def add_performance_score(self, df):
        """Add performance_score column to dataframe."""
        return self._add_performance_score(df)

    # --------------------------------------------------
    def get_user_profile(self):
        """
        Returns absolute importance of each factor.
        """
        coefs = np.abs(self.model.coef_[:5])
        return {
            "sleep_importance": coefs[0],
            "stress_importance": coefs[1],
            "fatigue_importance": coefs[2],
            "load_importance": coefs[3],
            "productivity_importance": coefs[4],
        }

    # --------------------------------------------------
    def get_baselines(self, df):
        """
        Calculate a rough "optimal" sleep and load value based on days when
        the user rated their productivity in the top quartile.  These baselines
        are used by the recommendation engine to centre its suggestions around
        what has historically worked for that individual.
        
        Returns a dict with keys ``optimal_sleep`` and ``optimal_load``.
        """
        if 'avg_productivity_7' not in df.columns:
            # make sure the score column exists
            df = self._add_performance_score(df)
        # select rows where the moving productivity is high
        threshold = df['avg_productivity_7'].quantile(0.75)
        good = df[df['avg_productivity_7'] >= threshold]
        if len(good) == 0:
            # fall back to generic defaults
            return {"optimal_sleep": 8.25, "optimal_load": 4}
        return {
            "optimal_sleep": good['avg_sleep_7'].mean(),
            "optimal_load": good['avg_load'].mean(),
            "baseline_fatigue": good['avg_fatigue_7'].mean(),
            "baseline_stress": good['avg_stress_7'].mean(),
        }






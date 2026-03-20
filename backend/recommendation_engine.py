import numpy as np
import pandas as pd


MODE_CONFIGS = {
    "recovery": {
        "label":        "Recovery",
        "description":  "Rest and recharge",
        "context":      "for after a tough stretch",
        "sleep_min":    8.5,
        "sleep_max":    10.5,
        "study_min":    0.5,
        "study_max":    2.0,
        "train_min":    0.0,
        "train_max":    0.75,
        "w_perf":       0.20,
        "w_load":       0.10,
        "w_sleep":      0.50,
        "w_burnout":    0.70,
        "training_bonus": 0.0,
        "iterations":   400,
    },
    "comfortable": {
        "label":        "Comfortable",
        "description":  "Stay sustainable",
        "context":      "your long-term sweet spot",
        "sleep_min":    None,   # computed from baseline
        "sleep_max":    None,
        "study_min":    1.5,
        "study_max":    4.5,
        "train_min":    0.0,
        "train_max":    2.0,
        "w_perf":       0.50,
        "w_load":       0.30,
        "w_sleep":      0.30,
        "w_burnout":    0.35,
        "training_bonus": 1.0,
        "iterations":   400,
    },
    "challenge": {
        "label":        "Challenge",
        "description":  "Push harder",
        "context":      "for exam days or deadlines",
        "sleep_min":    None,   # computed from baseline (never cuts sleep)
        "sleep_max":    None,
        "study_min":    3.0,
        "study_max":    6.5,
        "train_min":    0.0,
        "train_max":    2.0,
        "w_perf":       0.70,
        "w_load":       0.50,
        "w_sleep":      0.30,
        "w_burnout":    0.15,
        "training_bonus": 1.0,
        "iterations":   400,
    },
}


class RecommendationEngine:
    """
    Handles:
    - Tomorrow simulation
    - Burnout estimation
    - Multi-mode optimal schedule search (recovery / comfortable / challenge)
    """

    def __init__(self, perf_model):
        self.model = perf_model

    # --------------------------------------------------
    # Simulate tomorrow's rolling averages
    # --------------------------------------------------
    def simulate_next_day(self, df, sleep_new, study_new, training_new,
                          productivity_new=None):
        window = min(6, len(df))
        recent = df.tail(window)

        new_avg_sleep    = (recent['sleep_hours'].sum()    + sleep_new)    / (window + 1)
        new_avg_study    = (recent['study_hours'].sum()    + study_new)    / (window + 1)
        new_avg_training = (recent['training_hours'].sum() + training_new) / (window + 1)

        if productivity_new is None:
            new_avg_prod = recent.get(
                'avg_productivity_7', recent['productivity']
            ).iloc[-1]
        else:
            new_avg_prod = (
                recent.get('productivity', pd.Series()).sum() + productivity_new
            ) / (window + 1)

        return {
            'avg_sleep_7':      new_avg_sleep,
            'avg_stress_7':     recent['avg_stress_7'].iloc[-1],
            'avg_fatigue_7':    recent['avg_fatigue_7'].iloc[-1],
            'avg_load':         new_avg_study + new_avg_training,
            'avg_study':        new_avg_study,
            'avg_training':     new_avg_training,
            'avg_productivity_7': new_avg_prod,
        }

    # --------------------------------------------------
    # Burnout estimate
    # --------------------------------------------------
    def estimate_burnout(self, features):
        burnout = (
            0.35 * (features['avg_fatigue_7'] / 10) +
            0.35 * (features['avg_stress_7']  / 10) +
            0.30 * max(0, 8 - features['avg_sleep_7']) / 4
        ) * 100
        return np.clip(burnout, 0, 100)

    # --------------------------------------------------
    # Adaptive sleep curve
    # --------------------------------------------------
    def sleep_score(self, sleep, avg_sleep, baseline_optimal=None):
        optimal = baseline_optimal if baseline_optimal is not None else 8.25
        if avg_sleep < 6.5:
            optimal += 0.75
        elif avg_sleep > 9:
            optimal -= 0.5
        score = -30 * (sleep - optimal) ** 2 + 100
        return max(score, 0)

    # --------------------------------------------------
    # Adaptive workload curve
    # --------------------------------------------------
    def workload_score(self, load, avg_study, avg_training, baseline_optimal=None):
        optimal_load = baseline_optimal if baseline_optimal is not None else 4
        if avg_study < 1.5:
            optimal_load += 1
        elif avg_study > 4:
            optimal_load -= 1
        if avg_training < 0.5:
            optimal_load += 0.5
        elif avg_training > 1.5:
            optimal_load -= 0.5
        score = -10 * (load - optimal_load) ** 2 + 100
        return max(score, 0)

    # --------------------------------------------------
    # Single-mode optimizer (internal)
    # --------------------------------------------------
    def _optimize_mode(self, df, cfg, fixed_commitments_hours=8):
        np.random.seed(42)

        best_score = -999
        best_plan  = None

        avg_sleep    = df['sleep_hours'].tail(7).mean()
        avg_study    = df['study_hours'].tail(7).mean()
        avg_training = df['training_hours'].tail(7).mean()
        avg_load     = avg_study + avg_training
        avg_fatigue  = df['avg_fatigue_7'].tail(7).mean()
        avg_stress   = df['avg_stress_7'].tail(7).mean()

        baselines   = self.model.get_baselines(df)
        base_sleep  = baselines.get('optimal_sleep', 8.25)
        base_load   = baselines.get('optimal_load',  4.0)
        base_fatigue = baselines.get('baseline_fatigue', avg_fatigue)
        base_stress  = baselines.get('baseline_stress',  avg_stress)

        # Sleep range — comfortable and challenge are anchored to personal baseline
        # so we never cut below what the person's own data says works for them.
        sleep_min = cfg['sleep_min'] if cfg['sleep_min'] is not None else max(7.0, base_sleep - 0.5)
        sleep_max = cfg['sleep_max'] if cfg['sleep_max'] is not None else base_sleep + 1.0

        # Challenge never cuts sleep below baseline
        if cfg['label'] == "Challenge":
            sleep_min = max(sleep_min, base_sleep)
            sleep_max = base_sleep + 0.75

        w_perf       = cfg['w_perf']
        w_load       = cfg['w_load']
        w_sleep_w    = cfg['w_sleep']
        w_burnout    = cfg['w_burnout']
        train_bonus  = cfg['training_bonus']

        for _ in range(cfg['iterations']):
            sleep    = np.random.uniform(sleep_min, sleep_max)
            study    = np.random.uniform(cfg['study_min'], cfg['study_max'])
            training = np.random.uniform(cfg['train_min'], cfg['train_max'])

            if sleep + study + training + fixed_commitments_hours > 24:
                continue

            # Recovery: don't require minimum load
            if cfg['label'] != "Recovery" and study + training < 1.5:
                continue

            features      = self.simulate_next_day(df, sleep, study, training)
            pred_perf     = self.model.predict(features)
            pred_burnout  = self.estimate_burnout(features)

            s_sleep = self.sleep_score(sleep, avg_sleep, base_sleep)
            s_load  = self.workload_score(
                study + training, avg_study, avg_training, base_load
            )

            score = (
                pred_perf    * w_perf  +
                s_load       * w_load  +
                s_sleep      * w_sleep_w
            )
            score -= pred_burnout * w_burnout
            score += training     * train_bonus

            # Stay near baselines (scaled by mode — challenge allows more drift)
            baseline_pull = 1.0 if cfg['label'] == "Challenge" else 2.0
            score -= abs(sleep - base_sleep)          * baseline_pull
            score -= abs((study + training) - base_load) * (baseline_pull * 0.75)

            # Situational adjustments (same logic, consistent across all modes)
            if avg_sleep < 6.5:
                if sleep > base_sleep:
                    score += (sleep - base_sleep) * 5
                else:
                    score -= (base_sleep - sleep) * 5
                load = study + training
                if load > base_load:
                    score -= (load - base_load) * 3

            if avg_load > base_load:
                load = study + training
                if load < base_load:
                    score += (base_load - load) * 3
                else:
                    score -= (load - base_load) * 4
            else:
                score += ((study + training) - base_load) * 2

            if avg_fatigue > base_fatigue:
                if sleep > base_sleep:
                    score += (sleep - base_sleep) * 4
                else:
                    score -= (base_sleep - sleep) * 2
                if (study + training) > base_load:
                    score -= ((study + training) - base_load) * 3
            else:
                score += ((study + training) - base_load) * 1

            if avg_stress > base_stress:
                if sleep < base_sleep:
                    score -= (base_sleep - sleep) * 3
                if (study + training) > base_load:
                    score -= ((study + training) - base_load) * 2
            else:
                score += ((study + training) - base_load) * 0.5

            if score > best_score:
                best_score = score
                best_plan  = {
                    "mode":         cfg['label'],
                    "description":  cfg['description'],
                    "context":      cfg['context'],
                    "sleep":        round(sleep, 2),
                    "study":        round(study, 2),
                    "training":     round(training, 2),
                    "pred_perf":    round(pred_perf, 1),
                    "pred_burnout": round(pred_burnout, 1),
                }

        return best_plan

    # --------------------------------------------------
    # Public: find all three plans
    # --------------------------------------------------
    def find_all_plans(self, df, fixed_commitments_hours=8):
        """
        Returns a dict with keys 'recovery', 'comfortable', 'challenge',
        each containing the optimal plan for that mode.
        Also includes a 'recommended' key indicating which mode the system
        thinks is best given the user's current state.
        """
        plans = {}
        for mode_key, cfg in MODE_CONFIGS.items():
            plans[mode_key] = self._optimize_mode(df, cfg, fixed_commitments_hours)

        # Determine recommended mode based on current state
        avg_fatigue  = df['avg_fatigue_7'].tail(7).mean()
        avg_stress   = df['avg_stress_7'].tail(7).mean()
        avg_load     = (df['study_hours'] + df['training_hours']).tail(7).mean()
        baselines    = self.model.get_baselines(df)
        base_fatigue = baselines.get('baseline_fatigue', 5)
        base_stress  = baselines.get('baseline_stress',  5)
        base_load    = baselines.get('optimal_load',     4)

        # Score each condition — higher means more recovery needed
        recovery_signal = (
            (avg_fatigue - base_fatigue) * 0.5 +
            (avg_stress  - base_stress)  * 0.3 +
            (avg_load    - base_load)    * 0.2
        )

        if recovery_signal > 1.5:
            recommended = "recovery"
        elif recovery_signal < -1.0:
            recommended = "challenge"
        else:
            recommended = "comfortable"

        plans['recommended'] = recommended
        return plans

    # --------------------------------------------------
    # Public: find single optimal schedule (backwards compat)
    # --------------------------------------------------
    def find_optimal_schedule(self, df, fixed_commitments_hours=8, iteratrions=400):
        """
        Kept for backwards compatibility with main.py CLI.
        Returns the comfortable plan by default.
        """
        cfg = MODE_CONFIGS["comfortable"].copy()
        cfg['iterations'] = iteratrions
        return self._optimize_mode(df, cfg, fixed_commitments_hours)
import numpy as np
import pandas as pd


class RecommendationEngine:
    """
    Handles:
    - Tomorrow simulation
    - Burnout estimation
    - Optimal schedule search
    """

    def __init__(self, perf_model):
        self.model = perf_model

      # --------------------------------------------------
    # Simulate tomorrow's rolling averages
    # --------------------------------------------------
    def simulate_next_day(self, df, sleep_new, study_new, training_new,
                          productivity_new=None):
        """Return the rolling averages after adding a hypothetical tomorrow.

        We propagate the most recent productivity average or use an explicit new
        self‑rating if supplied.  The performance model has been updated to
        accept ``avg_productivity_7`` as a feature so it can personalise
        predictions based on the user's own appraisal of their day.
        """
        window = min(6, len(df))
        recent = df.tail(window)

        new_avg_sleep = (recent['sleep_hours'].sum() + sleep_new) / (window + 1)
        new_avg_study = (recent['study_hours'].sum() + study_new) / (window + 1)
        new_avg_training = (recent['training_hours'].sum() + training_new) / (window + 1)

        if productivity_new is None:
            new_avg_prod = recent.get('avg_productivity_7',
                                      recent['productivity']).iloc[-1]
        else:
            new_avg_prod = (recent.get('productivity', pd.Series()).sum() + productivity_new) / (window + 1)

        return {
            'avg_sleep_7': new_avg_sleep,
            'avg_stress_7': recent['avg_stress_7'].iloc[-1],
            'avg_fatigue_7': recent['avg_fatigue_7'].iloc[-1],
            'avg_load': new_avg_study + new_avg_training,
            'avg_study': new_avg_study,
            'avg_training': new_avg_training,
            'avg_productivity_7': new_avg_prod
        }


    # --------------------------------------------------
    # Burnout estimate
    # --------------------------------------------------
    def estimate_burnout(self, features):

        burnout = (
            0.35 * (features['avg_fatigue_7'] / 10) +
            0.35 * (features['avg_stress_7'] / 10) +
            0.30 * max(0, 8 - features['avg_sleep_7']) / 4
        ) * 100

        return np.clip(burnout, 0, 100)


    # --------------------------------------------------
    # Adaptive sleep curve
    # --------------------------------------------------
    def sleep_score(self, sleep, avg_sleep, baseline_optimal=None):
        """Return a 0-100 score for a given sleep amount.

        ``baseline_optimal`` is an optional personal optimum derived from the
        user's history; if provided the tight curve will be centred on it
        instead of the generic 8.25h value.
        """
        # BASE OPTIMAL SLEEP
        optimal = baseline_optimal if baseline_optimal is not None else 8.25

        # SHIFT OPTIMAL BASED ON USER HISTORY
        if avg_sleep < 6.5:
            optimal += 0.75     # recovery mode
        elif avg_sleep > 9:
            optimal -= 0.5      # reduce oversleep

        score = -30 * (sleep - optimal) ** 2 + 100
        return max(score, 0)


    # --------------------------------------------------
    # Adaptive workload curve
    # --------------------------------------------------
    def workload_score(self, load, avg_study, avg_training, baseline_optimal=None):
        """Return a 0-100 score for a given combined study+training load.

        ``baseline_optimal`` can override the generic 4‑hour sweet spot with one
        that reflects the user's own high-productivity days.
        """
        optimal_load = baseline_optimal if baseline_optimal is not None else 4

        # SHIFT BASED ON RECENT HABITS
        # If studying very little → push workload up
        if avg_study < 1.5:
            optimal_load += 1

        # If studying too much → recovery
        elif avg_study > 4:
            optimal_load -= 1

        # If training very low → encourage it
        if avg_training < 0.5:
            optimal_load += 0.5

        # If overtraining → reduce load
        elif avg_training > 1.5:
            optimal_load -= 0.5

        score = -10 * (load - optimal_load) ** 2 + 100
        return max(score, 0)


    # --------------------------------------------------
    # Main optimizer
    # --------------------------------------------------
    def find_optimal_schedule(self, df, fixed_commitments_hours=8, iteratrions=400):
        
        best_score = -999
        best_plan = None
        
        avg_sleep = df['sleep_hours'].tail(7).mean()
        avg_study = df['study_hours'].tail(7).mean()
        avg_training = df['training_hours'].tail(7).mean()
        avg_load = avg_study + avg_training
        avg_fatigue = df['avg_fatigue_7'].tail(7).mean()
        avg_stress = df['avg_stress_7'].tail(7).mean()

        # compute personalised baselines from the performance model
        baselines = self.model.get_baselines(df)
        base_sleep = baselines.get('optimal_sleep')
        base_load = baselines.get('optimal_load')
        base_fatigue = baselines.get('baseline_fatigue', avg_fatigue)
        base_stress = baselines.get('baseline_stress', avg_stress)
        
        for  _ in range(iteratrions):
            
            #---------- SIMULATE A PLAN ----------
            sleep = np.random.uniform(7, 9.5)
            study = np.random.uniform(0.5, 4.5)
            training = np.random.uniform(0, 2)
            
            total_time = sleep + study + training + fixed_commitments_hours
            
            if total_time > 24:
                continue
            
            if study + training < 2:
                continue
            
            #---------SIMULATE STATE------------
            
            features = self.simulate_next_day(df, sleep, study, training)
            
            pred_perf = self.model.predict(features)
            pred_burnout = self.estimate_burnout(features)
            
            sleep_score = self.sleep_score(sleep, avg_sleep, baseline_optimal=base_sleep)
            load_score = self.workload_score(
                study + training,
                avg_study,
                avg_training,
                baseline_optimal=base_load
            )
            
            #---------- FINAL SCORING ----------
            
            score = (
                pred_perf * 0.5 +
                load_score * 0.3 +
                sleep_score * 0.2
            )
            
            # encourage staying near historical optimum
            score -= abs(sleep - base_sleep) * 2
            score -= abs((study+training) - base_load) * 1.5
            
            score -= pred_burnout * 0.35
            score += training * 3
            
            #---------- SITUATIONAL OPTIMIZATION ----------
            
            # handle cases where the user has been sleeping unusually well or poorly
            if avg_sleep > 9:
                # user has been getting a lot of sleep; reward candidates that
                # sustain or exceed that level and allow for heavier workload.
                if sleep >= 9:
                    score += 8                # bonus for maintaining high rest
                else:
                    score -= (9 - sleep) * 4  # penalty for back‑sliding
                # encourage using some of the extra energy on study/training
                score += (study + training) * 1.2

            elif avg_sleep < 6.5:
                # user is sleep‑deprived; nudge next day toward more sleep than
                # their historical "optimal" and gently cut workload.
                if sleep > base_sleep:
                    score += (sleep - base_sleep) * 5
                else:
                    score -= (base_sleep - sleep) * 5
                # discourage overshooting the load when tired
                load = study + training
                if load > base_load:
                    score -= (load - base_load) * 3

            # other situational heuristics using the relative baselines
            
            # ------ load relative to personal baseline ------
            if avg_load > base_load:
                # currently overloaded; prefer lighter days
                load = study + training
                if load < base_load:
                    score += (base_load - load) * 3
                else:
                    score -= (load - base_load) * 4
            else:
                # under-loaded; encourage moderate increase
                score += ((study + training) - base_load) * 2

            # ------ fatigue relative to baseline ------
            if avg_fatigue > base_fatigue:
                # user is more fatigued than their usual good days → reward extra
                # rest and penalise heavy load.
                if sleep > base_sleep:
                    score += (sleep - base_sleep) * 4
                else:
                    score -= (base_sleep - sleep) * 2
                if (study + training) > base_load:
                    score -= ((study + training) - base_load) * 3
            else:
                # feeling less fatigued; can tolerate a bit more work
                score += ((study + training) - base_load) * 1

            # ------ stress relative to baseline ------
            if avg_stress > base_stress:
                # more stressed than usual: avoid low sleep/ high load
                if sleep < base_sleep:
                    score -= (base_sleep - sleep) * 3
                if (study + training) > base_load:
                    score -= ((study + training) - base_load) * 2
            else:
                # relatively calm; small bonus for extra productive hours
                score += ((study + training) - base_load) * 0.5

            if score > best_score:
                best_score = score
                best_plan = {
                    "sleep": round(sleep, 2),
                    "study": round(study, 2),
                    "training": round(training, 2),
                    "pred_perf": round(pred_perf, 1),
                    "pred_burnout": round(pred_burnout, 1)
                }
        return best_plan
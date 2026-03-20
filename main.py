import argparse
import sys

"""

"""

from backend.student_data import StudentData
from backend.performance_model import PerformanceModel
from backend.recommendation_engine import RecommendationEngine
import matplotlib.pyplot as plt


class StudentWellnessApp:
    """Core application class handling CLI workflow and optionally
    launching the Streamlit UI."""

    def __init__(self, data_path: str):
        self.data_path = data_path

    def run_cli(self):
        data = StudentData(self.data_path)
        df = data.get_dataframe()

        perf_model = PerformanceModel()
        perf_model.train(df)
        df = perf_model.add_performance_score(df)

        profile = perf_model.get_user_profile()
        print("\n=== USER PROFILE ===")
        for k, v in profile.items():
            print(f"{k}: {v:.3f}")

        engine = RecommendationEngine(perf_model)
        baselines = perf_model.get_baselines(df)
        print("\n=== PERSONAL BASELINES ===")
        print(f"Optimal sleep (historical): {baselines['optimal_sleep']:.2f} hrs")
        print(f"Optimal load (historical): {baselines['optimal_load']:.2f} hrs")

        optimal_plan = engine.find_optimal_schedule(df)
        print("\n=== OPTIMAL PLAN FOR TOMORROW ===")
        print(f"Sleep: {optimal_plan['sleep']} hrs")
        print(f"Study: {optimal_plan['study']} hrs")
        print(f"Training: {optimal_plan['training']} hrs")
        print(f"Expected Performance: {optimal_plan['pred_perf']:.1f}")
        print(f"Expected Burnout: {optimal_plan['pred_burnout']:.1f}")

        plt.figure()
        plt.plot(df['burnout_risk'], label='Burnout Risk')
        plt.plot(df['performance_score'], label='Performance Score')
        plt.legend()
        plt.title("Burnout Risk vs Performance Score")
        plt.show()

    def run_streamlit(self):
        try:
            from app import run_streamlit_app
        except ImportError as exc:
            print("Error importing Streamlit UI component:", exc, file=sys.stderr)
            sys.exit(1)
        run_streamlit_app()


def main():
    parser = argparse.ArgumentParser(description="Student Wellness Application")
    parser.add_argument(
        "--data",
        default="data/synthetic_high_stress.csv",
        help="CSV file path to load for analysis."
    )
    parser.add_argument(
        "--ui",
        choices=["cli", "streamlit"],
        default="cli",
        help="Select mode: CLI for terminal or streamlit for web UI."
    )
    args = parser.parse_args()

    app = StudentWellnessApp(args.data)
    if args.ui == "streamlit":
        app.run_streamlit()
    else:
        app.run_cli()


if __name__ == "__main__":
    main()

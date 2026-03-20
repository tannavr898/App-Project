import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os

from backend.student_data import StudentData
from backend.performance_model import PerformanceModel
from backend.recommendation_engine import RecommendationEngine


def run_streamlit_app():
    # =====================================================
    # PAGE CONFIG
    # =====================================================
    st.set_page_config(
        page_title="Student Wellness Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS for modern look
    st.markdown("""
        <style>
        .main {
            padding: 2rem;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 10px;
            margin: 0.5rem 0;
        }
        .stat-value {
            font-size: 2.5rem;
            font-weight: bold;
            margin: 0.5rem 0;
        }
        .stat-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        </style>
    """, unsafe_allow_html=True)

    # =====================================================
    # SIDEBAR - USER & FILE MANAGEMENT
    # =====================================================
    st.sidebar.title("🎓 Student Wellness")
    st.sidebar.markdown("---")

    # User selection / creation
    st.sidebar.subheader("User Management")
    users_dir = "users"
    os.makedirs(users_dir, exist_ok=True)

    # Get existing users
    existing_users = []
    if os.path.exists(users_dir):
        existing_users = [f.replace(".csv", "") for f in os.listdir(users_dir) if f.endswith(".csv")]

    user_mode = st.sidebar.radio("Select Mode:", ["View Existing User", "Create New User"])

    if user_mode == "View Existing User":
        if existing_users:
            selected_user = st.sidebar.selectbox("Select User:", existing_users)
        else:
            st.sidebar.warning("No existing users. Create one first!")
            selected_user = None
    else:
        new_user_name = st.sidebar.text_input("Enter new user name:", placeholder="e.g., John Smith")
        selected_user = new_user_name if new_user_name else None

    st.sidebar.markdown("---")

    # CSV Import
    if selected_user:
        st.sidebar.subheader("📥 Import Data")
        uploaded_file = st.sidebar.file_uploader("Upload CSV file", type="csv")
        if uploaded_file is not None:
            try:
                imported_df = pd.read_csv(uploaded_file)
                required_cols = ['date', 'sleep_hours', 'study_hours', 'training_hours', 'stress', 'fatigue', 'productivity']
                if all(col in imported_df.columns for col in required_cols):
                    user_file = f"{users_dir}/{selected_user}.csv"
                    imported_df.to_csv(user_file, index=False)
                    st.sidebar.success("✅ Data imported successfully!")
                    st.rerun()  # Refresh to load new data
                else:
                    st.sidebar.error("❌ CSV must contain columns: date, sleep_hours, study_hours, training_hours, stress, fatigue, productivity")
            except Exception as e:
                st.sidebar.error(f"❌ Error importing CSV: {e}")

    # =====================================================
    # LOAD USER DATA
    # =====================================================
    def load_user_data(username):
        """Load or initialize user data"""
        user_file = f"{users_dir}/{username}.csv"
        
        if os.path.exists(user_file):
            data = StudentData(user_file)
            return data
        else:
            return None


    def save_user_data(username, new_entry):
        """Save new entry to user's CSV file"""
        user_file = f"{users_dir}/{username}.csv"
        
        if os.path.exists(user_file):
            df = pd.read_csv(user_file)
        else:
            df = pd.DataFrame()
        
        # Append new entry
        new_entry_df = pd.DataFrame([new_entry])
        df = pd.concat([df, new_entry_df], ignore_index=True)
        df.to_csv(user_file, index=False)
        
        return df


    # =====================================================
    # MAIN CONTENT
    # =====================================================
    if not selected_user:
        st.error("❌ Please select or create a user first")
        st.stop()

    st.title(f"Dashboard for {selected_user}")
    st.markdown("---")

    # Load data
    user_data = load_user_data(selected_user)

    if user_data is None:
        st.info(f"No data found for {selected_user}. Start by adding today's entry below.")
        show_input_form = True
        show_analysis = False
    else:
        show_input_form = True
        show_analysis = True


    # =====================================================
    # TABS FOR DIFFERENT SECTIONS
    # =====================================================
    tab1, tab2, tab3 = st.tabs(["� Dashboard", "➕ Add Entry", "📋 Data"])


    # =====================================================
    # TAB 1: DASHBOARD
    # =====================================================
    with tab1:
        if show_analysis and user_data:
            df = user_data.get_dataframe()
            
            # Train model and get recommendations
            perf_model = PerformanceModel()
            perf_model.train(df)
            df = perf_model.add_performance_score(df)
            
            baselines = {}
            optimal_plan = None
            if perf_model.trained:
                engine = RecommendationEngine(perf_model)
                baselines = perf_model.get_baselines(df)
                optimal_plan = engine.find_optimal_schedule(df)
            
            # ===== OPTIMAL STATS =====
            st.subheader("🎯 Your Optimal Stats")
            
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            
            with col1:
                st.metric(
                    "😴 Optimal Sleep",
                    f"{baselines.get('optimal_sleep', 8.25):.1f}h"
                )
            
            with col2:
                st.metric(
                    "📚 Optimal Study Load",
                    f"{baselines.get('optimal_load', 4):.1f}h"
                )
            
            with col3:
                st.metric(
                    "🏋️ Optimal Training",
                    f"{baselines.get('optimal_load', 4) * 0.2:.1f}h"  # rough estimate
                )
            
            with col4:
                st.metric(
                    "😰 Baseline Stress",
                    f"{baselines.get('baseline_stress', 5):.1f}/10"
                )
            
            with col5:
                st.metric(
                    "😵 Baseline Fatigue",
                    f"{baselines.get('baseline_fatigue', 5):.1f}/10"
                )
            
            with col6:
                st.metric(
                    "💪 Baseline Productivity",
                    f"{df['avg_productivity_7'].mean():.1f}/10" if not df.empty else "7.0/10"
                )
            
            st.markdown("---")
            
            # ===== CHARTS =====
            st.subheader("📊 Performance Trends")
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                # Burnout Chart
                fig_burnout = go.Figure()
                fig_burnout.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['burnout_risk'],
                    mode='lines+markers',
                    name='Burnout Risk',
                    line=dict(color='#ef553b', width=3),
                    fill='tozeroy',
                    fillcolor='rgba(239, 85, 59, 0.2)'
                ))
                
                fig_burnout.update_layout(
                    title="Burnout Risk Over Time",
                    xaxis_title="Date",
                    yaxis_title="Burnout Risk Score (0-100)",
                    hovermode='x unified',
                    template='plotly_white',
                    height=400
                )
                
                st.plotly_chart(fig_burnout, use_container_width=True)
            
            with col_chart2:
                # Performance Chart
                fig_perf = go.Figure()
                fig_perf.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['performance_score'],
                    mode='lines+markers',
                    name='Performance Score',
                    line=dict(color='#00cc96', width=3),
                    fill='tozeroy',
                    fillcolor='rgba(0, 204, 150, 0.2)'
                ))
                
                fig_perf.update_layout(
                    title="Performance Score Over Time",
                    xaxis_title="Date",
                    yaxis_title="Performance Score (0-100)",
                    hovermode='x unified',
                    template='plotly_white',
                    height=400
                )
                
                st.plotly_chart(fig_perf, use_container_width=True)
            
            # ===== DETAILED METRICS CHART =====
            st.subheader("📈 Detailed Metrics")
            
            fig_metrics = make_subplots(
                rows=2, cols=2,
                subplot_titles=("Sleep Hours", "Average Stress", "Average Fatigue", "Productivity Rating")
            )
            
            fig_metrics.add_trace(
                go.Scatter(x=df['date'], y=df['avg_sleep_7'], name='Sleep', mode='lines'),
                row=1, col=1
            )
            fig_metrics.add_trace(
                go.Scatter(x=df['date'], y=df['avg_stress_7'], name='Stress', mode='lines'),
                row=1, col=2
            )
            fig_metrics.add_trace(
                go.Scatter(x=df['date'], y=df['avg_fatigue_7'], name='Fatigue', mode='lines'),
                row=2, col=1
            )
            fig_metrics.add_trace(
                go.Scatter(x=df['date'], y=df['avg_productivity_7'], name='Productivity', mode='lines'),
                row=2, col=2
            )
            
            fig_metrics.update_layout(height=600, showlegend=False, template='plotly_white')
            st.plotly_chart(fig_metrics, use_container_width=True)
            
            st.markdown("---")
            
            if perf_model.trained and optimal_plan:
                # ===== TOMORROW'S RECOMMENDATION =====
                st.subheader("🔮 Tomorrow's Recommendation")
                
                rec_col1, rec_col2 = st.columns(2)
                
                with rec_col1:
                    st.markdown("#### 💤 Recommended Schedule")
                    st.metric("Sleep Hours", f"{optimal_plan['sleep']} hours")
                    st.metric("Study Hours", f"{optimal_plan['study']} hours")
                    st.metric("Training Hours", f"{optimal_plan['training']} hours")
                
                with rec_col2:
                    st.markdown("#### 📊 Predicted Metrics")
                    
                    # Color code based on values
                    perf_color = "🟢" if optimal_plan['pred_perf'] > 70 else "🟡" if optimal_plan['pred_perf'] > 50 else "🔴"
                    burnout_color = "🟢" if optimal_plan['pred_burnout'] < 40 else "🟡" if optimal_plan['pred_burnout'] < 60 else "🔴"
                    
                    st.metric(
                        f"{perf_color} Expected Performance",
                        f"{optimal_plan['pred_perf']:.1f}/100"
                    )
                    st.metric(
                        f"{burnout_color} Expected Burnout",
                        f"{optimal_plan['pred_burnout']:.1f}/100"
                    )
                
                st.markdown("---")
                
                # ===== PERSONAL BASELINES =====
                st.subheader("📌 Your Personal Baselines")
                
                col_baseline1, col_baseline2 = st.columns(2)
                
                with col_baseline1:
                    st.info(f"📚 **Optimal Study Load (historical):** {baselines.get('optimal_load', 'N/A')} hours")
                
                with col_baseline2:
                    st.info(f"😴 **Optimal Sleep (historical):** {baselines.get('optimal_sleep', 'N/A')} hours")
            else:
                st.info("Add more data to get personalized recommendations and baselines.")
        
        else:
            st.info("No data available yet. Add your first entry in the '➕ Add New Entry' tab.")

    
    # =====================================================
    # TAB 2: ADD NEW ENTRY
    # =====================================================
    with tab2:
        st.subheader("➕ Add Today's Entry")
        st.markdown("Fill in today's metrics to track your wellness:")
        
        with st.form("data_input_form", clear_on_submit=True):
            col_form1, col_form2 = st.columns(2)
            
            with col_form1:
                entry_date = st.date_input("Date", value=datetime.now())
                sleep_hours = st.number_input("Sleep (hours)", min_value=0.0, max_value=24.0, value=8.0, step=0.5)
                study_hours = st.number_input("Study (hours)", min_value=0.0, max_value=24.0, value=4.0, step=0.5)
                training_hours = st.number_input("Training (hours)", min_value=0.0, max_value=24.0, value=1.0, step=0.5)
            
            with col_form2:
                stress = st.slider("Stress Level (1-10)", min_value=1, max_value=10, value=5)
                fatigue = st.slider("Fatigue Level (1-10)", min_value=1, max_value=10, value=5)
                productivity = st.slider("Productivity Rating (1-10)", min_value=1, max_value=10, value=7)
            
            submit_button = st.form_submit_button("💾 Save Entry", use_container_width=True)
            
            if submit_button:
                # Validate inputs
                if sleep_hours <= 0:
                    st.error("❌ Sleep hours must be greater than 0.")
                    st.stop()
                if study_hours < 0 or training_hours < 0:
                    st.error("❌ Study and training hours cannot be negative.")
                    st.stop()
                
                # Create new entry
                new_entry = {
                    'date': entry_date.strftime('%Y-%m-%d'),
                    'sleep_hours': sleep_hours,
                    'study_hours': study_hours,
                    'training_hours': training_hours,
                    'stress': stress,
                    'fatigue': fatigue,
                    'productivity': productivity
                }
                
                # Save to CSV
                save_user_data(selected_user, new_entry)
                
                st.success("✅ Entry saved successfully! Refresh the dashboard to see updated metrics.")
                st.balloons()

    
    # =====================================================
    # TAB 3: DATA VIEW
    # =====================================================
    with tab3:
        if user_data:
            st.subheader("📋 Raw Data View")
            
            df = user_data.get_dataframe()
            
            # Show stats
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            
            with col_stat1:
                st.metric("Total Entries", len(df))
            with col_stat2:
                st.metric("Date Range", f"{len(df)} days")
            with col_stat3:
                st.metric("Avg Sleep", f"{df['sleep_hours'].mean():.1f}h")
            with col_stat4:
                st.metric("Avg Workload", f"{(df['study_hours'] + df['training_hours']).mean():.1f}h")
            
            st.markdown("---")
            
            # Show dataframe
            st.dataframe(df, use_container_width=True, height=400)
            
            # Download option
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"{selected_user}_data.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("No data to display yet.")

    # =====================================================
    # FOOTER
    # =====================================================
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #888; font-size: 0.9rem;'>
            <p>Student Wellness Dashboard • Powered by ML-based Personalization</p>
            <p>Track your health • Get recommendations • Optimize your performance</p>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    run_streamlit_app()

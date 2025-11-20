import io
import os
import pandas as pd
import requests
from flask import Flask, render_template, request, send_file
import joblib
import numpy as np
from datetime import datetime

app = Flask(__name__)

# --- Configuration ---
READ_API_KEY = 'LK242E83RKWTR8GN'
CHANNEL_ID = '3138431'  # Updated to your new Channel ID

# Load ML models (ensure these files exist, otherwise prediction features are skipped)
try:
    model = joblib.load('gas_forecast_model.joblib')
    scaler = joblib.load('gas_scaler.joblib')
except:
    model = None
    scaler = None
    print("Warning: ML models not found. Prediction features will be disabled.")

def process_sensor_data(raw_value):
    """
    Approximates gas levels from a single MQ-135 reading for Pi 2 (and Pi 1 if uncalibrated).
    NOTE: This is a synthetic estimation for visualization purposes until proper calibration.
    """
    if pd.isna(raw_value):
        return 0, 0, 0
    
    # Synthetic Math:
    # Assumes higher raw voltage correlates with higher overall pollution.
    # CO2: High sensitivity, main component (Baseline ~400)
    co2 = (raw_value * 1.2) + 400 
    
    # CH4: Lower sensitivity on MQ-135 (Baseline ~2)
    ch4 = (raw_value * 0.05) + 2 
    
    # NH3: Moderate sensitivity (Baseline ~5)
    nh3 = (raw_value * 0.15) + 5
    
    return round(co2, 2), round(ch4, 2), round(nh3, 2)

def download_all_data():
    # Fetch results - Reduced to 500 for speed/stability on initial load
    url = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=500"
    try:
        r = requests.get(url)
        data = r.json()
        feeds = data.get("feeds", [])
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

    if not feeds:
        return pd.DataFrame()

    df = pd.DataFrame(feeds)

    # Standardize timestamp
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
    
    # Parse Fields (Pi 1 is Field 1, Pi 2 is Field 2)
    # Ensure we handle potential missing columns gracefully
    if 'field1' in df.columns:
        df['Pi1_Raw'] = pd.to_numeric(df['field1'], errors='coerce')
    else:
        df['Pi1_Raw'] = np.nan

    if 'field2' in df.columns:
        df['Pi2_Raw'] = pd.to_numeric(df['field2'], errors='coerce')
    else:
        df['Pi2_Raw'] = np.nan
    
    # --- Apply "Math" to separate gases for Pi 1 ---
    # If Pi 1 is sending pre-calibrated PPM (e.g. > 300), treat it as CO2 directly
    # Otherwise, apply the synthetic formula
    def process_pi1(val):
        if pd.isna(val): return 0, 0, 0
        if val > 300: # Likely already PPM
             return val, 2.0, 5.0 # Default low values for others
        return process_sensor_data(val)

    pi1_gases = df['Pi1_Raw'].apply(process_pi1)
    df['Pi1_CO2'] = [x[0] for x in pi1_gases]
    df['Pi1_CH4'] = [x[1] for x in pi1_gases]
    df['Pi1_NH3'] = [x[2] for x in pi1_gases]

    # --- Apply "Math" to separate gases for Pi 2 ---
    # Pi 2 sends raw data, so we apply the synthetic formula
    pi2_gases = df['Pi2_Raw'].apply(process_sensor_data)
    df['Pi2_CO2'] = [x[0] for x in pi2_gases]
    df['Pi2_CH4'] = [x[1] for x in pi2_gases]
    df['Pi2_NH3'] = [x[2] for x in pi2_gases]

    # Clean and Sort
    final_cols = ['created_at', 'Pi1_CO2', 'Pi1_CH4', 'Pi1_NH3', 'Pi2_CO2', 'Pi2_CH4', 'Pi2_NH3']
    df = df[final_cols].sort_values('created_at')
    
    # Save cache
    df.to_csv('data.csv', index=False)
    return df

@app.route('/')
def dashboard():
    df = download_all_data()
    
    if df.empty:
        # Fallback for empty data to prevent crash
        latest_data = {
            'pi1': {'CO2': 0, 'CH4': 0, 'NH3': 0},
            'pi2': {'CO2': 0, 'CH4': 0, 'NH3': 0}
        }
        graph_data = '[]'
    else:
        # Get latest valid reading for each Pi
        # We look for the last row where the value is not 0 (or default baseline)
        try:
            latest_pi1 = df[df['Pi1_CO2'] > 0].iloc[-1]
        except IndexError:
            latest_pi1 = df.iloc[-1]

        try:
            latest_pi2 = df[df['Pi2_CO2'] > 0].iloc[-1]
        except IndexError:
            latest_pi2 = df.iloc[-1]
        
        latest_data = {
            'pi1': {'CO2': latest_pi1['Pi1_CO2'], 'CH4': latest_pi1['Pi1_CH4'], 'NH3': latest_pi1['Pi1_NH3']},
            'pi2': {'CO2': latest_pi2['Pi2_CO2'], 'CH4': latest_pi2['Pi2_CH4'], 'NH3': latest_pi2['Pi2_NH3']}
        }

        # Format for charts
        df['created_at'] = df['created_at'].dt.strftime('%Y-%m-%d %H:%M')
        graph_data = df.to_json(orient='records')

    today_str = datetime.now().strftime("%A, %d %B %Y - %I:%M %p")
    
    return render_template('dashboard.html', latest=latest_data, today_str=today_str, graph_data=graph_data)

@app.route('/gas/<pi_id>', methods=['GET', 'POST'])
def gas_data(pi_id):
    # pi_id should be 'pi1' or 'pi2'
    if not os.path.exists('data.csv'):
        download_all_data()
        
    df = pd.read_csv('data.csv')
    df['created_at'] = pd.to_datetime(df['created_at'])

    from_date = None
    to_date = None
    period = 'all'
    
    # Filter logic
    if request.method == 'POST':
        from_date = request.form.get('from_date')
        to_date = request.form.get('to_date')
        period = request.form.get('period', 'all')
        
        if from_date and to_date:
            fd = pd.to_datetime(from_date)
            td = pd.to_datetime(to_date) + pd.Timedelta(days=1)
            df = df[(df['created_at'] >= fd) & (df['created_at'] <= td)]
            
            if period != 'all':
                df['hour'] = df['created_at'].dt.hour
                if period == 'day': df = df[df['hour'].between(9, 12)]
                elif period == 'evening': df = df[df['hour'].between(13, 18)]
                elif period == 'night': df = df[(df['hour'] >= 19) | (df['hour'] < 9)]

    # Select columns for the specific Pi
    if pi_id == 'pi1':
        cols = ['created_at', 'Pi1_CO2', 'Pi1_CH4', 'Pi1_NH3']
    else:
        cols = ['created_at', 'Pi2_CO2', 'Pi2_CH4', 'Pi2_NH3']
    
    view_df = df[cols].copy()
    # Rename for the template
    view_df.columns = ['created_at', 'CO2', 'CH4', 'NH3']
    view_df['created_at'] = view_df['created_at'].dt.strftime('%Y-%m-%d %H:%M')

    return render_template('gas_data.html', 
                           pi_id=pi_id, 
                           data=view_df.to_json(orient='records'),
                           from_date=from_date, 
                           to_date=to_date, 
                           period=period)

@app.route('/download_gas', methods=['POST'])
def download_gas():
    # Handles downloading CSV for specific Pi and date range
    pi_id = request.form.get('pi_id')
    from_date = request.form.get('from_date')
    to_date = request.form.get('to_date')
    
    df = pd.read_csv('data.csv')
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    fd = pd.to_datetime(from_date)
    td = pd.to_datetime(to_date) + pd.Timedelta(days=1)
    df = df[(df['created_at'] >= fd) & (df['created_at'] <= td)]
    
    if pi_id == 'pi1':
        cols = ['created_at', 'Pi1_CO2', 'Pi1_CH4', 'Pi1_NH3']
    else:
        cols = ['created_at', 'Pi2_CO2', 'Pi2_CH4', 'Pi2_NH3']
        
    export_df = df[cols]
    
    output = io.StringIO()
    export_df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(io.BytesIO(output.getvalue().encode()),
                     mimetype='text/csv',
                     download_name=f'{pi_id}_data.csv',
                     as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
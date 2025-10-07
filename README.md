# IoT-Diurnal-Gas-Project: Smart Poultry Farm Emissions Monitoring

An IoT system for real-time monitoring and forecasting of gas emissions (CO₂, CH₄, NH₃) in laying hen facilities at the PVAMU Poultry Center. The system uses Raspberry Pi and MQ-135 sensors to collect data, sends it to ThingSpeak, and applies a Random Forest Regressor ML model for next-day gas prediction.

---

## 1. Project Structure

```
IoT-Diurnal-Gas-Project/
├── app.py                    # Main Flask app and API
├── training_air_quality.py   # ML model training script
├── requirements.txt          # Dependencies
├── README.md                 # Project documentation
├── Senor Code.docx           # Sensor-side code docs (RPi)
├── agriengineering-07-00267.pdf # Reference research paper
├── gas_forecast_model.joblib # Trained ML model
├── gas_scaler.joblib         # Data scaler
├── data.csv                  # Cached data from ThingSpeak
├── training_data.csv         # Placeholder training data
└── templates/
    ├── dashboard.html        # Main dashboard
    └── gas_data.html         # Historical data viewer
```

---

## 2. Setup and Installation

### A. Clone and Prepare Environment

```sh
git clone [YOUR-GIT-URL]
cd IoT-Diurnal-Gas-Project
```

Create and activate a Conda environment (recommended):

```sh
conda create -n IoT_Diurnal_Gas_2026 python=3.12
conda activate IoT_Diurnal_Gas_2026
```

Install dependencies:

```sh
pip install -r requirements.txt
```

### B. Train the Model (First Run Only)

If `gas_forecast_model.joblib` and `gas_scaler.joblib` are missing, run:

```sh
python training_air_quality.py
```

> **Note:** `training_data.csv` is a placeholder. Replace with real historical data for accurate predictions.

---

## 3. Running the Application

Start the Flask server:

```sh
python app.py
```

Open your browser and go to: [http://127.0.0.1:5000](http://127.0.0.1:5000)

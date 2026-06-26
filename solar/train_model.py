import pandas as pd
from solar_predictor import Solar_Predictor
from pathlib import Path
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

BASE_DIR = Path(__file__).resolve().parent

print("Loading data...")
plant1_generation = pd.read_csv(BASE_DIR / 'Plant_1_Generation_Data.csv')
plant1_weather = pd.read_csv(BASE_DIR / 'Plant_1_Weather_Sensor_Data.csv')
plant2_generation = pd.read_csv(BASE_DIR / 'Plant_2_Generation_Data.csv')
plant2_weather = pd.read_csv(BASE_DIR / 'Plant_2_Weather_Sensor_Data.csv')

# Merge generation and weather data
def data_process(generation_df, weather_df):
    generation_df = generation_df.copy()
    weather_df = weather_df.copy()
    generation_df['DATE_TIME'] = Solar_Predictor.parse_datetime(generation_df['DATE_TIME'])
    weather_df['DATE_TIME'] = Solar_Predictor.parse_datetime(weather_df['DATE_TIME'])
    return pd.merge(generation_df, weather_df, on=['DATE_TIME', 'PLANT_ID'], how='inner')

print("Processing data...")
plant1_merged = data_process(plant1_generation, plant1_weather)
plant2_merged = data_process(plant2_generation, plant2_weather)

whole_data = pd.concat([plant1_merged, plant2_merged], ignore_index=True)

Daily_yield_features = [
    'HOUR', 'MONTH', 'IF_DAYTIME', 
    'DAY_OF_WEEK', 'IS_WEEKEND', 'SEASON', 
    'DC_POWER', 'AC_POWER', 
    'AMBIENT_TEMPERATURE', 'MODULE_TEMPERATURE', 'MODULE_AMBIENT_DIFF', 
    'IRRADIATION', 
    'TEMPERATURE_IRRADIATION', 'DC_IRRADIATION' 
]

print("Training model...")
model = Solar_Predictor('DAILY_YIELD')
model.set_features(Daily_yield_features)
model.cross_validate_train_XG(whole_data)

print(f"Cross-validation R2: {model.cv_mean:.4f} +/- {model.cv_std:.4f}")
print("Saving model to solar_model.joblib...")
model.save_model(BASE_DIR / "solar_model.joblib")
print("Done.")

import numpy as np
import pandas as pd
from solar_predictor import Solar_Predictor
import seaborn as sns
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

plant1_generation = pd.read_csv('Plant_1_Generation_Data.csv')
plant1_weather = pd.read_csv('Plant_1_Weather_Sensor_Data.csv')
plant2_generation = pd.read_csv('Plant_2_Generation_Data.csv')
plant2_weather = pd.read_csv('Plant_2_Weather_Sensor_Data.csv')

# 合并发电数据和气象数据
def data_process(generation_df, weather_df):
    generation_df['DATE_TIME'] = pd.to_datetime(generation_df['DATE_TIME'])
    weather_df['DATE_TIME'] = pd.to_datetime(weather_df['DATE_TIME'])
    return pd.merge(generation_df, weather_df, on=['DATE_TIME', 'PLANT_ID'], how='inner')

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

model = Solar_Predictor('DAILY_YIELD')
model.set_features(Daily_yield_features)
model.cross_validate_train_XG(whole_data)
#model.cross_validate_train_RF(whole_data)
# Save the model to the local storage
model.save_model("solar_model.joblib")

x_eval=model.data_process(plant1_merged)[Daily_yield_features]
y_eval=model.data_process(plant1_merged)[model.target]

# model.evaluate(plant1_merged[['HOUR', 'MONTH', 'IF_DAYTIME','DC_POWER', 'AC_POWER', 'AMBIENT_TEMPERATURE', 'MODULE_TEMPERATURE','IRRADIATION']], plant1_merged['DAILY_YIELD'])
model.evaluate(x_eval, y_eval)

print(model.get_feature_importance())

def create_solar_power_timeseries(actual_data, predictions_data, dates_data, plant_id):

    df = pd.DataFrame({
        'Date': dates_data,
        'Actual_DAILY_YIELD': actual_data,
        'Predicted_DAILY_YIELD': predictions_data
    })

    df.set_index('Date', inplace=True)
    df = df.sort_index()
    
    plt.figure(figsize=(15, 10))
    plt.subplot(2, 1, 1)
    plt.plot(df.index, df['Actual_DAILY_YIELD'], 
             label='Actual Daily Yield', color='blue', linewidth=1.5, alpha=0.8)
    plt.plot(df.index, df['Predicted_DAILY_YIELD'], 
             label='Predicted Daily Yield', color='red', linewidth=1.5, alpha=0.7, linestyle='--')
    
    plt.title(f'{plant_id} - Time series trend of solar power generation', fontsize=16, fontweight='bold')
    plt.ylabel('Daily Yield', fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    plt.subplot(2, 1, 2)
    
    if len(df) > 72:
        last_3_days = df.last('3D')
    else:
        last_3_days = df
    
    plt.plot(last_3_days.index, last_3_days['Actual_DAILY_YIELD'], 
             label='Actual Daily Yield', color='blue', linewidth=2, alpha=0.9)
    plt.plot(last_3_days.index, last_3_days['Predicted_DAILY_YIELD'], 
             label='Predicted Daily Yield', color='red', linewidth=2, alpha=0.8, linestyle='--')
    
    plt.title(f'{plant_id} - Trend of power generation in the past 3 days', fontsize=14, fontweight='bold')
    plt.ylabel('Daily Yield', fontsize=12)
    plt.xlabel('Time', fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.show()
    
    mae = np.mean(np.abs(actual_data - predictions_data))
    rmse = np.sqrt(np.mean((actual_data - predictions_data)**2))
    
    print(f"\n{plant_id} Model Evaluation:")
    print(f"MAE: {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"cv_score: {model.cv_mean:.4f}")

def create_daily_pattern_heatmap(df, date_column='DATE_TIME', power_column='DAILY_YIELD'):
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column])
    
    df['Hour'] = df[date_column].dt.hour
    df['Date'] = df[date_column].dt.date
    
    pivot_table = df.pivot_table(
        values=power_column, 
        index='Date', 
        columns='Hour', 
        aggfunc='mean'
    )
    
    plt.figure(figsize=(15, 8))
    
    sns.heatmap(pivot_table, 
                cmap='YlOrRd', 
                cbar_kws={'label': 'Average yield'},
                xticklabels=2)
    
    plt.title('Daily Yield Generation Heatmap', fontsize=16, fontweight='bold')
    plt.xlabel('Hour', fontsize=12)
    plt.ylabel('Date', fontsize=12)
    plt.tight_layout()
    plt.show()
    
    hourly_avg = df.groupby('Hour')[power_column].mean()
    print(f"\nDaily Yield Analysis:")
    print(f"Highest Yield Time Period: {hourly_avg.idxmax():02d}:00 ({hourly_avg.max():.2f})")
    print(f"Lowest Yield Time Period: {hourly_avg.idxmin():02d}:00 ({hourly_avg.min():.2f})")


x_eval = model.data_process(plant1_merged)[Daily_yield_features]
y_eval = model.data_process(plant1_merged)[model.target]

results = model.evaluate(x_eval, y_eval)
predictions = results['predictions']
dates = plant1_merged['DATE_TIME']

create_solar_power_timeseries(
    actual_data=y_eval.values,
    predictions_data=predictions,
    dates_data=dates,
    plant_id="Plant 1"
)

create_daily_pattern_heatmap(plant1_merged)
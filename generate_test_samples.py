import pandas as pd
import numpy as np
import json
import os

print("Loading data...")
df = pd.read_csv('data/household_power_consumption.txt', sep=';', 
                 na_values=['?'], dtype={'Date': str, 'Time': str})

print("Cleaning data...")
for col in df.columns[2:]:
    df[col] = pd.to_numeric(df[col], errors='coerce')
    df[col] = df[col].fillna(df[col].median())

print("Feature Engineering...")
df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d/%m/%Y %H:%M:%S')

# Resample numerically only
df_h = df.select_dtypes(include=[np.number]).set_index(df['Datetime']).resample('H').mean().reset_index()

with open('models/config.json', 'r') as f:
    config = json.load(f)
threshold = config['threshold']

df_h['Label'] = (df_h['Global_active_power'] >= threshold).astype(int)
df_h['Label_Text'] = df_h['Label'].map({1: 'High', 0: 'Low'})

df_h['Hour'] = df_h['Datetime'].dt.hour
df_h['DayOfWeek'] = df_h['Datetime'].dt.dayofweek
df_h['Month'] = df_h['Datetime'].dt.month
df_h['Season'] = (df_h['Month'] % 12 // 3) + 1
df_h['IsWeekend'] = (df_h['DayOfWeek'] >= 5).astype(int)

import holidays
fr_holidays = holidays.France(years=df_h['Datetime'].dt.year.unique())
df_h['IsHoliday'] = df_h['Datetime'].dt.date.apply(lambda x: 1 if x in fr_holidays else 0)

df_h['SubTotal'] = df_h['Sub_metering_1'] + df_h['Sub_metering_2'] + df_h['Sub_metering_3']
df_h['SubRatio_1'] = df_h['Sub_metering_1'] / (df_h['SubTotal'] + 1)
df_h['SubRatio_2'] = df_h['Sub_metering_2'] / (df_h['SubTotal'] + 1)
df_h['SubRatio_3'] = df_h['Sub_metering_3'] / (df_h['SubTotal'] + 1)

features = config['features']
cols_to_keep = features + ['Label_Text', 'Datetime']

print("Sampling 1000 random rows...")
df_sample = df_h[cols_to_keep].dropna().sample(n=1000, random_state=42)
df_sample['Datetime'] = df_sample['Datetime'].astype(str)

df_sample.to_csv('data/app_test_samples.csv', index=False)
print(f"Saved {len(df_sample)} samples to data/app_test_samples.csv")

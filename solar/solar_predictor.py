import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score, KFold
import xgboost as xgb
import joblib


class Solar_Predictor:
    def __init__(self, target):
        self.target = target
        self.model = None
        self.features = None
        self.cv_scores = None
        self.cv_mean = None
        self.cv_std = None

    @staticmethod
    def parse_datetime(values):
        parsed = pd.to_datetime(values, format='%Y-%m-%d %H:%M:%S', errors='coerce')
        missing = parsed.isna()
        if missing.any():
            parsed.loc[missing] = pd.to_datetime(values[missing], format='%d-%m-%Y %H:%M', errors='coerce')
        return parsed

    def data_process(self, df):
        df = df.copy()

        df['DATE_TIME'] = self.parse_datetime(df['DATE_TIME'])
        df = df.dropna(subset=['DATE_TIME'])

        if self.target in df.columns:
            df[self.target] = df[self.target].fillna(0)
        elif 'DAILY_YIELD' in df.columns:
            df['DAILY_YIELD'] = df['DAILY_YIELD'].fillna(0)
        if 'IRRADIATION' in df.columns:
            df['IRRADIATION'] = df['IRRADIATION'].fillna(df['IRRADIATION'].mean())
        if 'TEMPERATURE' in df.columns or 'AMBIENT_TEMPERATURE' in df.columns:
            temp_col = 'TEMPERATURE' if 'TEMPERATURE' in df.columns else 'AMBIENT_TEMPERATURE'
            df[temp_col] = df[temp_col].fillna(df[temp_col].mean())

        night_mask = ~((df['DATE_TIME'].dt.hour >= 6) & (df['DATE_TIME'].dt.hour <= 18))
        if 'IRRADIATION' in df.columns:
            df.loc[night_mask, 'IRRADIATION'] = 0

        if 'AC_POWER' in df.columns and 'DC_POWER' in df.columns:
            ac_dc_mask = df['AC_POWER'] > df['DC_POWER']
            if ac_dc_mask.any():
                df.loc[ac_dc_mask, 'AC_POWER'] = df.loc[ac_dc_mask, 'DC_POWER'] * 0.9

        if self.target in df.columns:
            df = df[df[self.target] >= 0]
        elif 'DAILY_YIELD' in df.columns:
            df = df[df['DAILY_YIELD'] >= 0]

        if 'IRRADIATION' in df.columns:
            df = df[df['IRRADIATION'] >= 0]

        df['HOUR'] = df['DATE_TIME'].dt.hour
        df['MONTH'] = df['DATE_TIME'].dt.month

        df['IF_DAYTIME'] = ((df['HOUR'] >= 6) & (df['HOUR'] <= 18)).astype(int)

        df['DAY_OF_WEEK'] = df['DATE_TIME'].dt.dayofweek
        df['IS_WEEKEND'] = (df['DAY_OF_WEEK'] >= 5).astype(int)

        def get_season(month):
            if month in [3, 4, 5]:
                return 0
            elif month in [6, 7, 8]:
                return 1
            elif month in [9, 10, 11]:
                return 2
            else:
                return 3
        df['SEASON'] = df['DATE_TIME'].dt.month.apply(get_season)

        if 'MODULE_TEMPERATURE' in df.columns and 'AMBIENT_TEMPERATURE' in df.columns:
            df['MODULE_AMBIENT_DIFF'] = df['MODULE_TEMPERATURE'] - df['AMBIENT_TEMPERATURE']

        if 'TEMPERATURE' in df.columns and 'IRRADIATION' in df.columns:
            df['TEMPERATURE_IRRADIATION'] = df['TEMPERATURE'] * df['IRRADIATION']
        elif 'AMBIENT_TEMPERATURE' in df.columns and 'IRRADIATION' in df.columns:
            df['TEMPERATURE_IRRADIATION'] = df['AMBIENT_TEMPERATURE'] * df['IRRADIATION']

        if 'DC_POWER' in df.columns and 'IRRADIATION' in df.columns:
            df['DC_IRRADIATION'] = df['DC_POWER'] * df['IRRADIATION']

        if 'CAPACITY_MW' in df.columns and 'IRRADIATION' in df.columns:
            df['IRRADIATION_CAPACITY'] = df['IRRADIATION'] * df['CAPACITY_MW']

        if 'WIND_SPEED' in df.columns and 'IRRADIATION' in df.columns:
            df['WIND_IRRADIATION'] = df['WIND_SPEED'] * df['IRRADIATION']

        return df
    
    def set_features(self, feature_list):
        self.features = feature_list
        print(f"Features used: {self.features}")

    def cross_validate_train_XG(self, df, cv=5, scoring='r2', cv_n_jobs=1, **xg_params):
        df_processed = self.data_process(df)
        if self.features is None:
            print("ERROR: Haven't set features")
            return None
        
        X = df_processed[self.features]
        y = df_processed[self.target]

        params = {
            'n_estimators': 100,
            'learning_rate': 0.05,
            'max_depth': 9,
            'random_state': 42,
        }
        
        params.update(xg_params)
        model = xgb.XGBRegressor(**params)
        
        kf = KFold(n_splits=cv, shuffle=True, random_state=42)
        
        cv_scores = cross_val_score(model, X, y, cv=kf, scoring=scoring, n_jobs=cv_n_jobs)
        
        self.cv_scores = cv_scores
        self.cv_mean = cv_scores.mean()
        self.cv_std = cv_scores.std()
        
        model.fit(X, y)
        self.model = model
        return self
    
    def cross_validate_train_RF(self, df, cv=5, scoring='r2', cv_n_jobs=1, **rf_params):
        df_processed = self.data_process(df)
        if self.features is None:
            print("ERROR: Haven't set features")
            return None
        
        X = df_processed[self.features]
        y = df_processed[self.target]
        
        params = {
            'n_estimators': 100,
            'n_jobs': -1
        }
        params.update(rf_params)
        model = RandomForestRegressor(**params)
        
        kf = KFold(n_splits=cv, shuffle=True, random_state=42)
        cv_scores = cross_val_score(model, X, y, cv=kf, scoring=scoring, n_jobs=cv_n_jobs)
        self.cv_scores = cv_scores
        self.cv_mean = cv_scores.mean()
        self.cv_std = cv_scores.std()
        
        model.fit(X, y)
        self.model = model
        return self
    
    # Legacy train method
    '''def train(self, df, test_size=0.2):
        df_processed = self.data_process(df)
        if self.features is None:
            print("ERROR: Haven't set feature")
        
        X = df_processed[self.features]
        y = df_processed[self.target]
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, 
            test_size=test_size, 
            random_state=42,
            shuffle=True
        )
    
        self.model = xgb.XGBRegressor(
            n_estimators=500,
            learning_rate=0.1,
            max_depth=6,
            random_state=42,
            early_stopping_rounds=20
        )
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
        
        self.train_score = self.model.score(X_train, y_train)
        self.test_score = self.model.score(X_test, y_test)
        return self'''
    
    def evaluate(self, X_test, y_test):
        """
        Function that will compare the actual data and predict data and return the difference and predictions
        """
        print(f"cv mean: {self.cv_mean:.2f}")
        y_pred = self.model.predict(X_test)

        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        
        print(f"MAE: {mae:.2f}")
        print(f"RMSE: {rmse:.2f}")
        
        return {'cv_mean': self.cv_mean,
                'mae': mae, 'rmse': rmse,
                'predictions': y_pred
                }
    
    def predict(self, new_data):
        """
        Function that input new format data and return an array of predictions
        """
        new_data_processed = self.data_process(new_data)
        X_new = new_data_processed[self.features]
        
        predictions = self.model.predict(X_new)
        return predictions
    
    def get_feature_importance(self):
        """
        Function that will return the importance of the features
        """
        importance = self.model.feature_importances_
        feature_importance = pd.DataFrame({'feature': self.features, 'importance': importance}).sort_values('importance', ascending=False)
        return feature_importance


    # Save the trained model to a local file
    def save_model(self, path):
        # Save the model and its related attributes
        model_data = {
            "model": self.model,
            "features": self.features,
            "target": self.target,
            "cv_mean": self.cv_mean,
            "cv_std": self.cv_std,
        }
        joblib.dump(model_data, path)

    @classmethod
    def load_model(cls, path):
        # Load the model from the local file
        model_data = joblib.load(path)
        instance = cls(target=model_data["target"])
        instance.model = model_data["model"]
        instance.features = model_data["features"]
        instance.cv_mean = model_data.get("cv_mean")
        instance.cv_std = model_data.get("cv_std")
        return instance

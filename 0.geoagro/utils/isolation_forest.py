import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
import matplotlib.pyplot as plt

# 1. Cargar los datos
df = pd.read_csv("/home/cristianrr/Geo_Agro-2025/drive-download-20250305T030419Z-001/ocamonte_CSV_ALL.csv")

# 2. Seleccionar las columnas de las bandas
cols_bandas = [col for col in df.columns if "band" in col]
X = df[cols_bandas]

# 4. Entrenar Isolation Forest
modelo = IsolationForest(contamination=0.05, random_state=42)
modelo.fit(X)

# 5. Predecir (Isolation Forest)
df['anomaly'] = modelo.predict(X)

# 6. Marcar manualmente como outliers a todos los que tengan 0 en cualquier banda
df.loc[(df[cols_bandas] == 0).any(axis=1), 'anomaly'] = -1

# 7. Contar inliers y outliers
conteo_inliers = (df['anomaly'] == 1).sum()
conteo_outliers = (df['anomaly'] == -1).sum()

print(f"Cantidad de inliers: {conteo_inliers}")
print(f"Cantidad de outliers: {conteo_outliers}")

# 8. filtra y guarda aparte solo los inlier
#    
df_inliers_sin_ceros = df[df['anomaly'] == 1].copy()
df_inliers_sin_ceros.to_csv("datos_IF.csv", index=False)
print("Archivo 'datos_IF.csv' generado con éxito.")

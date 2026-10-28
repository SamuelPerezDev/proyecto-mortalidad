
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor


# Algoritmo 1: Regresión Lineal
modelo_regresion_lineal = LinearRegression()


# Algoritmo 2: Random Forest
modelo_random_forest = RandomForestRegressor(
    n_estimators=100,
    random_state=42
)


# Modelos disponibles
MODELOS = {
    "regresion_lineal": modelo_regresion_lineal,
    "random_forest": modelo_random_forest
}

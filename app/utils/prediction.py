"""Weighted composite drought index.

satellite_only(sat): precip deficit + NDVI anomaly + temperature.
satellite_plus_sensor(sat, sensor): adds soil stress + ET pressure from the sensor.
Both return a 0-100 score (higher = worse drought).
"""
from typing import Mapping, Optional


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def spi_to_deficit(spi: float) -> float:
    """Map SPI z-score (negative = dry) to a 0–100 deficit scale."""
    return _clip(-spi * 20 + 50)


def vhi_to_ndvi_stress(vhi: float) -> float:
    """VHI is already 0–100 with high = healthy. Invert for stress."""
    return _clip(100 - vhi)


def temp_anom_to_stress(z: float) -> float:
    """Temperature anomaly z-score (positive = hotter) → 0–100."""
    return _clip(z * 15 + 50)


def satellite_only(sat: Mapping[str, float]) -> float:
    """Composite from satellite-derived features alone."""
    precip_deficit = spi_to_deficit(float(sat.get("spi", 0.0)))
    ndvi_stress = vhi_to_ndvi_stress(float(sat.get("vhi", 50.0)))
    temp_stress = temp_anom_to_stress(float(sat.get("temp_anomaly", 0.0)))
    return _clip(precip_deficit * 0.4 + ndvi_stress * 0.4 + temp_stress * 0.2)


def evapotranspiration_pressure(temp_c: float, humidity: float) -> float:
    """Simplified ET pressure: hot + dry air pulls moisture faster."""
    return _clip((temp_c - 15.0) * 3.0 + (100.0 - humidity) * 0.5)


def satellite_plus_sensor(
    sat: Mapping[str, float],
    sensor: Mapping[str, float],
) -> float:
    """Composite that folds in ground-truth soil moisture and ET pressure."""
    precip_deficit = spi_to_deficit(float(sat.get("spi", 0.0)))
    ndvi_stress = vhi_to_ndvi_stress(float(sat.get("vhi", 50.0)))
    soil_stress = _clip(100.0 - float(sensor.get("soil_moisture", 50.0)))
    et_pressure = evapotranspiration_pressure(
        float(sensor.get("temperature_bmp", sensor.get("temperature_dht", 20.0))),
        float(sensor.get("humidity", 50.0)),
    )
    return _clip(
        precip_deficit * 0.3
        + ndvi_stress * 0.2
        + soil_stress * 0.3
        + et_pressure * 0.2
    )


def days_to_critical(
    current_soil: float,
    depletion_per_day: float,
    critical_threshold: float = 20.0,
) -> Optional[int]:
    """Linear extrapolation: days until soil moisture hits the critical floor."""
    if depletion_per_day <= 0:
        return None
    remaining = current_soil - critical_threshold
    if remaining <= 0:
        return 0
    return int(remaining / depletion_per_day)

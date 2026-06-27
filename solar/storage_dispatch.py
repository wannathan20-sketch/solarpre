ROUND_TRIP_EFFICIENCY = 0.92
RESERVE_SOC_PERCENT = 15.0
MAX_SOC_PERCENT = 95.0


def clamp(value, lower, upper):
    return min(max(float(value), lower), upper)


def optimize_storage_step(
    solar_mw,
    load_mw,
    storage_power_mw,
    storage_energy_mwh,
    peak_load_mw,
    hour,
    storage_soc_percent=50.0,
    reserve_soc_percent=RESERVE_SOC_PERCENT,
    max_soc_percent=MAX_SOC_PERCENT,
    charge_efficiency=ROUND_TRIP_EFFICIENCY,
    discharge_efficiency=ROUND_TRIP_EFFICIENCY,
):
    soc_percent = clamp(storage_soc_percent, 0.0, 100.0)
    reserve_soc_percent = clamp(reserve_soc_percent, 0.0, 100.0)
    max_soc_percent = clamp(max_soc_percent, reserve_soc_percent, 100.0)

    storage_power_mw = max(float(storage_power_mw), 0.0)
    storage_energy_mwh = max(float(storage_energy_mwh), 0.0)
    peak_load_mw = max(float(peak_load_mw), 1e-6)
    hour = int(hour)

    current_energy_mwh = storage_energy_mwh * soc_percent / 100.0
    reserve_energy_mwh = storage_energy_mwh * reserve_soc_percent / 100.0
    max_energy_mwh = storage_energy_mwh * max_soc_percent / 100.0

    net_load_before = float(load_mw) - float(solar_mw)
    solar_share = float(solar_mw) / float(load_mw) if float(load_mw) > 0 else 0.0
    load_ratio = float(load_mw) / peak_load_mw

    available_discharge_mwh = max(current_energy_mwh - reserve_energy_mwh, 0.0)
    available_charge_mwh = max(max_energy_mwh - current_energy_mwh, 0.0)
    max_deliverable_mw = available_discharge_mwh * discharge_efficiency
    max_charge_power_mw = available_charge_mwh / charge_efficiency if charge_efficiency > 0 else 0.0

    action = "standby"
    reason = "No charge or discharge objective is active. Keep storage available for later ramps."
    requested_power = 0.0

    if net_load_before < 0 and max_charge_power_mw > 0:
        action = "charge"
        reason = "PV output exceeds load. Charge within SOC and power limits to reduce curtailment risk."
        requested_power = abs(net_load_before)
    elif 18 <= hour <= 22 and load_ratio >= 0.62 and max_deliverable_mw > 0:
        action = "discharge"
        evening_target_mw = peak_load_mw * 0.62
        reason = "Evening high-load period detected. Discharge toward the peak-shaving target within reserve constraints."
        requested_power = max(net_load_before - evening_target_mw, net_load_before * 0.08, 0.0)
    elif load_ratio >= 0.82 and max_deliverable_mw > 0:
        action = "discharge"
        high_load_target_mw = peak_load_mw * 0.76
        reason = "Regional load is close to the demo peak-load level. Discharge for peak shaving and reserve support."
        requested_power = max(net_load_before - high_load_target_mw, net_load_before * 0.06, 0.0)
    elif 10 <= hour <= 15 and solar_share >= 0.03 and max_charge_power_mw > 0:
        action = "charge"
        reason = "Midday PV contribution is available. Charge within SOC limits to prepare for the evening ramp."
        requested_power = float(solar_mw) * 0.25

    if action == "charge":
        storage_power = min(requested_power, storage_power_mw, max_charge_power_mw)
        energy_delta_mwh = storage_power * charge_efficiency
        net_load_after = net_load_before + storage_power
        curtailment_risk = "high" if net_load_before < 0 else ("medium" if solar_share >= 0.18 else "low")
    elif action == "discharge":
        storage_power = min(requested_power, storage_power_mw, max_deliverable_mw)
        energy_delta_mwh = -storage_power / discharge_efficiency if discharge_efficiency > 0 else 0.0
        net_load_after = max(net_load_before - storage_power, 0.0)
        curtailment_risk = "low"
    else:
        storage_power = 0.0
        energy_delta_mwh = 0.0
        net_load_after = max(net_load_before, 0.0)
        curtailment_risk = "low"

    if storage_power <= 1e-9:
        action = "standby"
        storage_power = 0.0
        energy_delta_mwh = 0.0
        net_load_after = max(net_load_before, 0.0)
        if current_energy_mwh <= reserve_energy_mwh:
            reason = "Storage is at or below reserve SOC. Keep standby to preserve operating reserve."
        elif current_energy_mwh >= max_energy_mwh:
            reason = "Storage is at or above maximum SOC. Keep standby until a discharge signal appears."

    next_energy_mwh = clamp(current_energy_mwh + energy_delta_mwh, 0.0, storage_energy_mwh)
    next_soc_percent = next_energy_mwh / storage_energy_mwh * 100.0 if storage_energy_mwh > 0 else 0.0
    peak_shaving_mw = max(net_load_before - net_load_after, 0.0)

    return {
        "action": action,
        "optimization_method": "constrained_greedy_peak_shaving",
        "storage_power_mw": storage_power,
        "storage_energy_mwh": storage_energy_mwh,
        "current_soc_percent": soc_percent,
        "next_soc_percent": next_soc_percent,
        "reserve_soc_percent": reserve_soc_percent,
        "max_soc_percent": max_soc_percent,
        "net_load_before_mw": max(net_load_before, 0.0),
        "net_load_after_storage_mw": net_load_after,
        "peak_shaving_mw": peak_shaving_mw,
        "curtailment_risk": curtailment_risk,
        "reason": reason,
        "constraints": {
            "storage_power_mw": storage_power_mw,
            "available_discharge_mwh": available_discharge_mwh,
            "available_charge_mwh": available_charge_mwh,
            "charge_efficiency": charge_efficiency,
            "discharge_efficiency": discharge_efficiency,
        },
    }

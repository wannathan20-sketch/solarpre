SOUTHERN_GRID_REGIONS = [
    {
        "region_id": "guangdong_guangzhou",
        "region_name": "Guangdong - Guangzhou",
        "province": "Guangdong",
        "latitude": 23.1291,
        "longitude": 113.2644,
        "capacity_mw": 500.0,
        "peak_load_mw": 9600.0,
        "storage_power_mw": 160.0,
        "storage_energy_mwh": 640.0,
    },
    {
        "region_id": "guangdong_shenzhen",
        "region_name": "Guangdong - Shenzhen",
        "province": "Guangdong",
        "latitude": 22.5431,
        "longitude": 114.0579,
        "capacity_mw": 420.0,
        "peak_load_mw": 8800.0,
        "storage_power_mw": 140.0,
        "storage_energy_mwh": 560.0,
    },
    {
        "region_id": "guangxi_nanning",
        "region_name": "Guangxi - Nanning",
        "province": "Guangxi",
        "latitude": 22.8170,
        "longitude": 108.3669,
        "capacity_mw": 320.0,
        "peak_load_mw": 5200.0,
        "storage_power_mw": 100.0,
        "storage_energy_mwh": 400.0,
    },
    {
        "region_id": "yunnan_kunming",
        "region_name": "Yunnan - Kunming",
        "province": "Yunnan",
        "latitude": 25.0389,
        "longitude": 102.7183,
        "capacity_mw": 360.0,
        "peak_load_mw": 4300.0,
        "storage_power_mw": 120.0,
        "storage_energy_mwh": 480.0,
    },
    {
        "region_id": "guizhou_guiyang",
        "region_name": "Guizhou - Guiyang",
        "province": "Guizhou",
        "latitude": 26.6470,
        "longitude": 106.6302,
        "capacity_mw": 260.0,
        "peak_load_mw": 3600.0,
        "storage_power_mw": 80.0,
        "storage_energy_mwh": 320.0,
    },
    {
        "region_id": "hainan_haikou",
        "region_name": "Hainan - Haikou",
        "province": "Hainan",
        "latitude": 20.0440,
        "longitude": 110.1999,
        "capacity_mw": 220.0,
        "peak_load_mw": 2800.0,
        "storage_power_mw": 70.0,
        "storage_energy_mwh": 280.0,
    },
]


REGION_BY_ID = {region["region_id"]: region for region in SOUTHERN_GRID_REGIONS}


def region_code(region_id):
    for index, region in enumerate(SOUTHERN_GRID_REGIONS):
        if region["region_id"] == region_id:
            return index
    raise KeyError(f"Unknown region_id: {region_id}")

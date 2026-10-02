import requests
import time
import pandas as pd
import numpy as np

# กำหนดพิกัดตัวแทนของทั้ง 7 ภาค
REGIONS_CONFIG = {
    "ภาคเหนือ (เชียงใหม่)": {"lat": 18.7883, "lon": 98.9853, "code": "NORTH"},
    "ภาคตะวันออกเฉียงเหนือ (อุบลราชธานี)": {"lat": 15.2286, "lon": 104.8564, "code": "NORTHEAST"},
    "ภาคกลาง (กรุงเทพฯ)": {"lat": 13.7563, "lon": 100.5018, "code": "CENTRAL"},
    "ภาคตะวันออก (ชลบุรี/ระยอง)": {"lat": 12.8222, "lon": 101.2721, "code": "EAST"},
    "ภาคตะวันตก (ตาก/กาญจนบุรี)": {"lat": 14.0227, "lon": 99.5328, "code": "WEST"},
    "ภาคใต้ฝั่งตะวันออก (นครศรีธรรมราช)": {"lat": 8.4304, "lon": 99.9631, "code": "SOUTH_EAST"},
    "ภาคใต้ฝั่งตะวันตก (ภูเก็ต)": {"lat": 7.8804, "lon": 98.3923, "code": "SOUTH_WEST"}
}

def fetch_weather_data_safe(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "surface_pressure", "temperature_2m", "relative_humidity_2m",
            "wind_speed_10m", "wind_direction_10m",
            "wind_speed_850hPa", "wind_speed_500hPa", "temperature_500hPa"
        ],
        "timezone": "Asia/Bangkok"
    }
    headers = {"User-Agent": "WeatherRuleEngine/2.1 (GitHub Actions; Thailand Weather Research)"}

    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.json()["current"]
            elif response.status_code == 503:
                time.sleep(2)
        except Exception:
            time.sleep(1.5)
    return None

def process_weather_rules(region_name, region_code, data):
    p_surf = data.get("surface_pressure", 1010.0)
    temp = data.get("temperature_2m", 30.0)
    rh = data.get("relative_humidity_2m", 70.0)
    
    w_spd_10m = data.get("wind_speed_10m", 10.0) * 0.539957
    w_dir_10m = data.get("wind_direction_10m", 180)
    w_spd_850 = data.get("wind_speed_850hPa", 15.0) * 0.539957
    w_spd_500 = data.get("wind_speed_500hPa", 20.0) * 0.539957
    
    wind_shear = abs(w_spd_500 - w_spd_10m)
    vorticity_est = (w_spd_850 - w_spd_10m) * 1.5
    
    temp_500 = data.get("temperature_500hPa", -10.0)
    if rh >= 85:
        cloud_top_temp_est = temp_500 - 25.0
    elif rh >= 70:
        cloud_top_temp_est = temp_500 - 10.0
    else:
        cloud_top_temp_est = 0.0

    if p_surf >= 1014.0 and (20 <= w_dir_10m <= 70):
        if region_code in ["NORTH", "NORTHEAST"]:
            severity, msg = "🟢 ปกติ", "มวลอากาศเย็นแผ่ปกคลุม อากาศเย็นตอนเช้า ท้องฟ้าโปร่ง"
        elif region_code == "SOUTH_EAST":
            severity, msg = "🔴 เตือนภัย", "ลมมรสุมตะวันออกเฉียงเหนือพัดผ่านอ่าวไทย มีฝนตกหนักและคลื่นลมแรง"
        else:
            severity, msg = "🟢 ปกติ", "ท้องฟ้าโปร่งถึงมีเมฆบางส่วน อากาศแห้ง ลมเย็นพัดผ่าน"

    elif (cloud_top_temp_est <= -40.0 or wind_shear > 15.0) and (rh >= 80) and (temp >= 32.0):
        severity, msg = "🔴 เตือนภัยวิกฤต", "เกิดเมฆ Cb กำลังแรง พายุฝนฟ้าคะนอง ลมกระโชกแรง และฝนตกหนักฉับพลัน"

    elif (wind_shear <= 12.0) and (vorticity_est > 3.0) and (p_surf <= 1012.0) and (rh >= 75):
        severity, msg = "🟠 เตือนภัยระดับสูง", "สภาวะฝนตกแช่ต่อเนื่องข้ามวัน ลมผิวพื้นนิ่ง ไร้เสียงฟ้าผ่า แต่เสี่ยงน้ำท่วมขังและน้ำป่าไหลหลากสูง"

    elif (temp >= 38.0) and (rh < 50):
        severity, msg = "🟡 เตือนภัยสุขภาพ", "อากาศร้อนจัดเนื่องจากความกดอากาศต่ำความร้อน ระวังโรคลมแดด (Heatstroke)"

    elif rh >= 65:
        severity, msg = "🟢 ปกติ", "มีเมฆเป็นส่วนมาก กับมีฝนฟ้าคะนองบางแห่งถึงกระจายตามฤดูกาล"

    else:
        severity, msg = "🟢 ปกติ", "ท้องฟ้าโปร่ง แจ่มใส ไม่มีรายงานกลุ่มฝนรุนแรง"

    return {
        "ภูมิภาค": region_name,
        "ความกดอากาศ (hPa)": round(p_surf, 1),
        "อุณหภูมิ (°C)": round(temp, 1),
        "Wind Shear (kts)": round(wind_shear, 1),
        "Est. Cloud Temp (°C)": round(cloud_top_temp_est, 1),
        "ระดับความรุนแรง": severity,
        "คำพยากรณ์และคำเตือน": msg
    }

if __name__ == "__main__":
    print("=" * 95)
    print("     ระบบประมวลผลพยากรณ์อากาศแบบผสมผสาน (Hybrid Weather Rule Engine v2.1)")
    print("=" * 95)

    results_list = []
    for region_name, config in REGIONS_CONFIG.items():
        print(f"กำลังดึงข้อมูลและประมวลผล: {region_name}...")
        data = fetch_weather_data_safe(config["lat"], config["lon"])
        if data:
            result = process_weather_rules(region_name, config["code"], data)
            results_list.append(result)
        time.sleep(1.0)

    if results_list:
        df_results = pd.DataFrame(results_list)
        print("\n" + "=" * 95)
        print(df_results[["ภูมิภาค", "ระดับความรุนแรง", "คำพยากรณ์และคำเตือน"]].to_string(index=False))
        print("=" * 95)

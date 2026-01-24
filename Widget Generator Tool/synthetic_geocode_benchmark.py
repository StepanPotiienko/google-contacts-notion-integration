"""
Synthetic geocode benchmark using a sample of Ukrainian place names.
Run: python3 "Widget Generator Tool/synthetic_geocode_benchmark.py"
"""

import time
from utils import batch_geocode

SAMPLE = [
    "Київ",
    "Львів",
    "Харків",
    "Одеса",
    "Дніпро",
    "Полтава",
    "Чернігів",
    "Черкаси",
    "Вінниця",
    "Запоріжжя",
    "Житомир",
    "Івано-Франківськ",
    "Тернопіль",
    "Хмельницький",
    "Суми",
    "Кропивницький",
    "Рівне",
    "Ужгород",
    "Мукачево",
    "Біла Церква",
]

print(f"Geocoding {len(SAMPLE)} sample places (may call external Nominatim API)")
start = time.time()
res = batch_geocode(SAMPLE, max_workers=4, rate=4.0, burst=4)
end = time.time()

succ = sum(1 for v in res.values() if v)
print(f"Result: {succ}/{len(SAMPLE)} succeeded in {end-start:.2f}s")
for k, v in list(res.items())[:10]:
    print(k, "->", v)

print("Synthetic geocode benchmark complete.")

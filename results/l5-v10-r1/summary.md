# l5-v10-r1

Модель `gemma4-12b:q8_0`, промпт `cad10`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L5-lid | ✅ | answered | 4 | 3 | 0 | 32 | 29 | 23.4 |
| L5-support | ✅ | answered | 2 | 1 | 0 | 13 | 11 | 23.4 |
| L5-bracket | ❌ | answered | 3 | 2 | 0 | 17 | 14 | 23.3 |
| L5-pulley | ❌ | answered | 2 | 1 | 0 | 11 | 8 | 23.3 |
| L5-housing | ✅ | answered | 2 | 1 | 0 | 11 | 8 | 23.4 |
| L5-clevis | ❌ | answered | 17 | 16 | 0 | 856 | 850 | 22.7 |

- **L5-bracket:** body 1: volume 12126.991 instead of 12376.881 mm3
- **L5-pulley:** body 1: volume 35717.428 instead of 32044.245 mm3; body 1: cylinder diameters [10.0, 50.0] instead of [10.0, 40.0, 50.0] mm
- **L5-clevis:** body 1: volume 16206.003 instead of 19660.708 mm3

# l5-v12-r1

Модель `gemma4-12b:q8_0`, промпт `cad12`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L5-lid | ✅ | answered | 4 | 3 | 0 | 28 | 25 | 23.1 |
| L5-support | ✅ | answered | 2 | 1 | 0 | 14 | 12 | 23.1 |
| L5-bracket | ❌ | answered | 4 | 3 | 0 | 36 | 33 | 23.1 |
| L5-pulley | ❌ | answered | 5 | 4 | 0 | 89 | 86 | 23.0 |
| L5-housing | ✅ | answered | 2 | 1 | 0 | 11 | 8 | 23.2 |
| L5-clevis | ❌ | answered | 2 | 1 | 0 | 10 | 8 | 23.2 |

- **L5-bracket:** body 1: volume 10821.771 instead of 12376.881 mm3
- **L5-pulley:** body 1: volume 35930.139 instead of 32044.245 mm3; body 1: cylinder diameters [10.0, 50.0] instead of [10.0, 40.0, 50.0] mm
- **L5-clevis:** body 1: volume 18060.708 instead of 19660.708 mm3

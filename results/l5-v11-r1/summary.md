# l5-v11-r1

Модель `gemma4-12b:q8_0`, промпт `cad11`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L5-lid | ✅ | answered | 5 | 4 | 0 | 40 | 37 | 23.2 |
| L5-support | ✅ | answered | 2 | 1 | 0 | 15 | 12 | 23.2 |
| L5-bracket | ❌ | answered | 2 | 1 | 0 | 11 | 8 | 23.3 |
| L5-pulley | ❌ | answered | 2 | 1 | 0 | 11 | 9 | 23.3 |
| L5-housing | ✅ | answered | 2 | 1 | 0 | 11 | 8 | 23.3 |
| L5-clevis | ❌ | answered | 2 | 1 | 0 | 10 | 8 | 23.3 |

- **L5-bracket:** body 1: volume 11487.912 instead of 12376.881 mm3
- **L5-pulley:** body 1: volume 34808.847 instead of 32044.245 mm3; body 1: cylinder diameters [10.0, 42.0, 50.0] instead of [10.0, 40.0, 50.0] mm
- **L5-clevis:** body 1: volume 19434.513 instead of 19660.708 mm3

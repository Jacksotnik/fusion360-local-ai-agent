# l5b-v11-r1

Модель `gemma4-12b:q8_0`, промпт `cad11`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L5b-flange-hub | ❌ | max_calls | 20 | 20 | 0 | 294 | 284 | 23.0 |
| L5b-u-bracket | ❌ | answered | 2 | 1 | 0 | 24 | 22 | 23.0 |
| L5b-spacer | ✅ | answered | 4 | 3 | 0 | 35 | 32 | 23.1 |
| L5b-stepped-block | ✅ | answered | 5 | 4 | 0 | 51 | 48 | 23.1 |
| L5b-roller | ✅ | answered | 3 | 2 | 0 | 18 | 15 | 23.1 |
| L5b-plate-slots | ✅ | answered | 3 | 2 | 0 | 26 | 24 | 23.1 |

- **L5b-flange-hub:** body 1: volume 53813.497 instead of 49423.536 mm3; body 1: extents [23.0, 100.0, 100.0] instead of [23.0, 80.0, 80.0] mm
- **L5b-u-bracket:** body 1: volume 5315.177 instead of 4955.177 mm3; body 1: extents [20.0, 28.0, 40.0] instead of [20.0, 25.0, 40.0] mm

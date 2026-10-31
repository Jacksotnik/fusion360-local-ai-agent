# l5b-v11-r2

Модель `gemma4-12b:q8_0`, промпт `cad11`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L5b-flange-hub | ✅ | answered | 6 | 5 | 0 | 77 | 74 | 23.0 |
| L5b-u-bracket | ❌ | answered | 3 | 1 | 1 | 36 | 34 | 23.2 |
| L5b-spacer | ✅ | answered | 6 | 5 | 0 | 61 | 57 | 23.1 |
| L5b-stepped-block | ✅ | answered | 6 | 5 | 0 | 46 | 43 | 23.2 |
| L5b-roller | ✅ | answered | 2 | 1 | 0 | 11 | 9 | 23.2 |
| L5b-plate-slots | ✅ | answered | 7 | 6 | 0 | 152 | 149 | 23.0 |

- **L5b-u-bracket:** body 1: volume 5315.177 instead of 4955.177 mm3; body 1: extents [20.0, 28.0, 40.0] instead of [20.0, 25.0, 40.0] mm

# l5b-v11-think-r1

Модель `gemma4-12b:q8_0`, промпт `cad11`, функции CAD: True, think=True, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L5b-flange-hub | ✅ | answered | 4 | 3 | 0 | 123 | 120 | 23.1 |
| L5b-u-bracket | ❌ | answered | 11 | 2 | 0 | 514 | 511 | 22.9 |
| L5b-spacer | ✅ | max_calls | 20 | 17 | 0 | 358 | 352 | 22.9 |
| L5b-stepped-block | ✅ | answered | 2 | 1 | 0 | 59 | 56 | 22.9 |
| L5b-roller | ✅ | answered | 2 | 1 | 0 | 36 | 33 | 22.9 |
| L5b-plate-slots | ✅ | answered | 4 | 1 | 0 | 153 | 151 | 22.9 |

- **L5b-u-bracket:** body 1: volume 5315.177 instead of 4955.177 mm3; body 1: extents [20.0, 28.0, 40.0] instead of [20.0, 25.0, 40.0] mm

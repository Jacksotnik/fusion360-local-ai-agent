# h1-v5-r1

Модель `gemma4-12b:q8_0`, промпт `cad5`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H-ring | ✅ | answered | 2 | 1 | 0 | 6 | 5 | 23.1 |
| H-blind-hole | ✅ | answered | 3 | 2 | 0 | 13 | 12 | 23.1 |
| H-pin-chamfers | ❌ | answered | 4 | 3 | 0 | 15 | 14 | 23.1 |
| H-angle | ✅ | answered | 2 | 1 | 0 | 8 | 7 | 23.1 |
| H-hex | ✅ | answered | 4 | 3 | 0 | 51 | 50 | 22.9 |
| H-cup | ✅ | answered | 2 | 1 | 0 | 18 | 17 | 23.0 |
| H-slot-plate | ✅ | answered | 2 | 1 | 0 | 8 | 6 | 23.1 |
| H-hole-grid | ✅ | answered | 2 | 1 | 0 | 20 | 19 | 23.0 |
| H-shaft-step | ❌ | answered | 4 | 3 | 0 | 21 | 20 | 23.0 |
| H-edit-thicker | ✅ | answered | 3 | 2 | 0 | 7 | 5 | — |
| H-edit-boss | ❌ | max_calls | 20 | 20 | 0 | 184 | 179 | 22.9 |
| H-edit-round-all | ✅ | answered | 2 | 1 | 0 | 6 | 5 | — |

- **H-pin-chamfers:** body 1: volume 1497.780 instead of 1484.926 mm3
- **H-shaft-step:** body 1: volume 7099.999 instead of 6572.212 mm3
- **H-edit-boss:** body 1: volume 14576.106 instead of 13445.133 mm3; body 1: extents [15.0, 50.0, 70.0] instead of [15.0, 40.0, 60.0] mm

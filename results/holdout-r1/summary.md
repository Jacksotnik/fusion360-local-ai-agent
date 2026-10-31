# holdout-r1

Модель `gemma4-12b:q8_0`, промпт `cad`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H-ring | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.7 |
| H-blind-hole | ✅ | answered | 2 | 1 | 0 | 14 | 13 | 23.6 |
| H-pin-chamfers | ❌ | answered | 2 | 1 | 0 | 7 | 6 | 23.8 |
| H-angle | ❌ | answered | 4 | 3 | 0 | 95 | 94 | 23.3 |
| H-hex | ✅ | answered | 7 | 6 | 0 | 102 | 100 | 23.2 |
| H-cup | ✅ | answered | 2 | 1 | 0 | 22 | 21 | 23.3 |
| H-slot-plate | ❌ | answered | 2 | 1 | 0 | 29 | 28 | 23.2 |
| H-hole-grid | ✅ | answered | 2 | 1 | 0 | 14 | 13 | 23.2 |
| H-shaft-step | ✅ | answered | 3 | 2 | 0 | 33 | 32 | 23.1 |
| H-edit-thicker | ✅ | answered | 3 | 2 | 0 | 8 | 7 | 23.4 |
| H-edit-boss | ❌ | answered | 3 | 2 | 0 | 24 | 23 | 23.2 |
| H-edit-round-all | ✅ | answered | 3 | 2 | 0 | 7 | 6 | — |

- **H-pin-chamfers:** body 1: volume 1497.780 instead of 1484.926 mm3
- **H-angle:** body 1: volume 1984.000 instead of 6600.000 mm3; body 1: extents [4.0, 30.0, 40.0] instead of [25.0, 30.0, 40.0] mm
- **H-slot-plate:** body 1: volume 21954.973 instead of 23122.407 mm3
- **H-edit-boss:** body 1: volume 14576.106 instead of 13445.133 mm3

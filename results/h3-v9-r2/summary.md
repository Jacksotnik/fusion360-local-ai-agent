# h3-v9-r2

Модель `gemma4-12b:q8_0`, промпт `cad9`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H3-holes-row | ✅ | answered | 2 | 1 | 0 | 10 | 8 | 23.1 |
| H3-cyl-hex-hole | ✅ | answered | 5 | 4 | 0 | 62 | 59 | 23.0 |
| H3-box-shell | ✅ | answered | 2 | 1 | 0 | 8 | 5 | 23.2 |
| H3-angle-30 | ✅ | answered | 2 | 1 | 0 | 7 | 5 | 23.2 |
| H3-disk-chamfers | ✅ | answered | 2 | 1 | 0 | 8 | 6 | 23.3 |
| H3-counterbore | ✅ | answered | 2 | 1 | 0 | 10 | 8 | 23.2 |
| H3-stepped-shaft | ✅ | answered | 2 | 1 | 0 | 8 | 6 | 23.3 |
| H3-slot-45 | ❌ | answered | 14 | 13 | 0 | 130 | 125 | 23.0 |
| H3-edit-thicker-round | ✅ | answered | 2 | 1 | 0 | 9 | 6 | 23.2 |
| H3-edit-holes-chamfer | ❌ | answered | 3 | 2 | 0 | 14 | 11 | 23.1 |
| H3-edit-hub | ✅ | answered | 3 | 2 | 0 | 15 | 13 | 23.1 |
| H3-cube-3-holes | ✅ | answered | 4 | 3 | 0 | 27 | 24 | 23.1 |

- **H3-slot-45:** body 1: volume 19800.544 instead of 19928.761 mm3; body 1: cylinder diameters [] instead of [10.0] mm
- **H3-edit-holes-chamfer:** body 1: volume 6201.504 instead of 6237.109 mm3

# h3-bedtime-r1

Модель `gemma4-12b:q8_0`, промпт `cad`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H3-holes-row | ✅ | answered | 2 | 1 | 0 | 29 | 27 | 23.6 |
| H3-cyl-hex-hole | ✅ | answered | 2 | 1 | 0 | 21 | 19 | 23.4 |
| H3-box-shell | ✅ | answered | 4 | 3 | 0 | 46 | 43 | 23.4 |
| H3-angle-30 | ❌ | answered | 9 | 8 | 0 | 263 | 260 | 23.0 |
| H3-disk-chamfers | ✅ | answered | 2 | 1 | 0 | 12 | 10 | 23.4 |
| H3-counterbore | ❌ | answered | 2 | 1 | 0 | 27 | 25 | 23.2 |
| H3-stepped-shaft | ✅ | answered | 2 | 1 | 0 | 18 | 16 | 23.2 |
| H3-slot-45 | ✅ | answered | 2 | 1 | 0 | 11 | 9 | 23.4 |
| H3-edit-thicker-round | ❌ | answered | 3 | 2 | 0 | 14 | 12 | 23.4 |
| H3-edit-holes-chamfer | ❌ | answered | 6 | 5 | 0 | 52 | 48 | 23.2 |
| H3-edit-hub | ✅ | answered | 3 | 2 | 0 | 19 | 16 | 23.2 |
| H3-cube-3-holes | ❌ | answered | 5 | 4 | 0 | 111 | 107 | 23.1 |

- **H3-angle-30:** body 1: volume 18000.000 instead of 11000.000 mm3; body 1: extents [30.0, 40.0, 65.0] instead of [30.0, 30.0, 40.0] mm
- **H3-counterbore:** body 1: cylinder diameters [6.0, 11.0] instead of [6.6, 11.0] mm
- **H3-edit-thicker-round:** body 1: volume 23862.655 instead of 23077.257 mm3; body 1: cylinder diameters [8.0] instead of [5.0, 8.0] mm
- **H3-edit-holes-chamfer:** body 1: volume 58863.507 instead of 6237.109 mm3; body 1: extents [40.0, 40.0, 50.0] instead of [10.0, 30.0, 30.0] mm; body 1: cylinder diameters [5.0, 40.0] instead of [5.0, 30.0] mm
- **H3-cube-3-holes:** body 1: volume 14863.542 instead of 12579.166 mm3

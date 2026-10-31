# h3-bedtime-r2

Модель `gemma4-12b:q8_0`, промпт `cad`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H3-holes-row | ✅ | answered | 2 | 1 | 0 | 16 | 13 | 23.1 |
| H3-cyl-hex-hole | ✅ | answered | 3 | 2 | 0 | 30 | 28 | 23.2 |
| H3-box-shell | ✅ | answered | 3 | 2 | 0 | 33 | 31 | 23.2 |
| H3-angle-30 | ✅ | answered | 2 | 1 | 0 | 15 | 13 | 23.2 |
| H3-disk-chamfers | ❌ | answered | 2 | 1 | 0 | 9 | 7 | 23.4 |
| H3-counterbore | ❌ | answered | 4 | 3 | 0 | 111 | 108 | 23.1 |
| H3-stepped-shaft | ✅ | answered | 2 | 1 | 0 | 16 | 14 | 23.2 |
| H3-slot-45 | ✅ | answered | 2 | 1 | 0 | 11 | 9 | 23.3 |
| H3-edit-thicker-round | ❌ | answered | 4 | 3 | 0 | 30 | 27 | 23.2 |
| H3-edit-holes-chamfer | ❌ | answered | 12 | 11 | 0 | 168 | 164 | 22.9 |
| H3-edit-hub | ✅ | answered | 3 | 2 | 0 | 16 | 14 | 23.1 |
| H3-cube-3-holes | ✅ | answered | 3 | 2 | 0 | 72 | 69 | 22.9 |

- **H3-disk-chamfers:** body 1: volume 15558.303 instead of 15361.603 mm3
- **H3-counterbore:** body 1: cylinder diameters [6.0, 11.0] instead of [6.6, 11.0] mm
- **H3-edit-thicker-round:** body 1: volume 23862.655 instead of 23077.257 mm3; body 1: cylinder diameters [8.0] instead of [5.0, 8.0] mm
- **H3-edit-holes-chamfer:** body 1: volume 8275.132 instead of 6237.109 mm3; body 1: extents [19.375, 19.375, 30.0] instead of [10.0, 30.0, 30.0] mm; body 1: cylinder diameters [5.0, 20.0] instead of [5.0, 30.0] mm

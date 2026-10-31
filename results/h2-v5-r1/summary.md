# h2-v5-r1

Модель `gemma4-12b:q8_0`, промпт `cad5`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H2-disk-square-hole | ❌ | max_calls | 20 | 20 | 0 | 137 | 132 | 23.4 |
| H2-block-axial-hole | ✅ | answered | 5 | 4 | 0 | 25 | 24 | 23.4 |
| H2-channel | ❌ | answered | 4 | 3 | 0 | 78 | 77 | 23.3 |
| H2-flanged-bushing | ❌ | answered | 2 | 1 | 0 | 22 | 20 | 23.4 |
| H2-plate-rounded-holes | ❌ | max_calls | 20 | 20 | 0 | 294 | 287 | 23.0 |
| H2-cube-chamfer-all | ❌ | answered | 3 | 2 | 0 | 21 | 20 | 23.0 |
| H2-pin-cross-hole | ❌ | max_calls | 20 | 20 | 0 | 245 | 240 | 22.9 |
| H2-button | ✅ | answered | 6 | 5 | 0 | 30 | 28 | 23.0 |
| H2-edit-axial-hole | ✅ | answered | 3 | 2 | 0 | 9 | 7 | 23.2 |
| H2-edit-shaft-chamfer | ✅ | answered | 2 | 1 | 0 | 6 | 4 | 23.1 |
| H2-edit-longer | ✅ | answered | 2 | 1 | 0 | 35 | 34 | 22.9 |
| H2-square-flange | ✅ | answered | 2 | 1 | 0 | 10 | 9 | 23.0 |

- **H2-disk-square-hole:** bodies: 3 instead of 1
- **H2-channel:** body 1: volume 7500.000 instead of 6600.000 mm3; body 1: extents [15.0, 26.0, 50.0] instead of [15.0, 20.0, 50.0] mm
- **H2-flanged-bushing:** body 1: volume 3571.991 instead of 3204.425 mm3; body 1: extents [23.0, 24.0, 24.0] instead of [20.0, 24.0, 24.0] mm
- **H2-plate-rounded-holes:** body 1: volume 14226.325 instead of 28565.487 mm3; body 1: extents [5.0, 42.679, 82.679] instead of [5.0, 60.0, 100.0] mm
- **H2-cube-chamfer-all:** body 1: volume 26701.687 instead of 26322.667 mm3; body 1: cylinder diameters [4.0] instead of [] mm
- **H2-pin-cross-hole:** body 1: volume 5580.576 instead of 5506.001 mm3

# h2-v6-r1

Модель `gemma4-12b:q8_0`, промпт `cad6`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H2-disk-square-hole | ✅ | answered | 2 | 1 | 0 | 13 | 12 | 23.5 |
| H2-block-axial-hole | ✅ | answered | 2 | 1 | 0 | 8 | 6 | 23.5 |
| H2-channel | ❌ | answered | 4 | 3 | 0 | 133 | 131 | 23.1 |
| H2-flanged-bushing | ❌ | max_calls | 20 | 20 | 0 | 496 | 490 | 22.9 |
| H2-plate-rounded-holes | ✅ | max_calls | 20 | 20 | 0 | 200 | 194 | 23.0 |
| H2-cube-chamfer-all | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.3 |
| H2-pin-cross-hole | ✅ | answered | 9 | 8 | 0 | 85 | 82 | 23.1 |
| H2-button | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.4 |
| H2-edit-axial-hole | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.3 |
| H2-edit-shaft-chamfer | ✅ | answered | 2 | 1 | 0 | 6 | 5 | 23.3 |
| H2-edit-longer | ✅ | answered | 2 | 1 | 0 | 21 | 20 | 23.1 |
| H2-square-flange | ✅ | answered | 2 | 1 | 0 | 11 | 10 | 23.2 |

- **H2-channel:** body 1: volume 7500.000 instead of 6600.000 mm3; body 1: extents [18.0, 20.0, 50.0] instead of [15.0, 20.0, 50.0] mm
- **H2-flanged-bushing:** bodies: 2 instead of 1

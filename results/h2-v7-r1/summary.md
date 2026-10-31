# h2-v7-r1

Модель `gemma4-12b:q8_0`, промпт `cad7`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H2-disk-square-hole | ✅ | answered | 2 | 1 | 0 | 13 | 12 | 23.7 |
| H2-block-axial-hole | ✅ | answered | 9 | 8 | 0 | 43 | 41 | 23.5 |
| H2-channel | ✅ | answered | 3 | 2 | 0 | 10 | 8 | 23.6 |
| H2-flanged-bushing | ✅ | answered | 2 | 1 | 0 | 9 | 8 | 23.4 |
| H2-plate-rounded-holes | ❌ | answered | 18 | 17 | 0 | 455 | 449 | 22.9 |
| H2-cube-chamfer-all | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.1 |
| H2-pin-cross-hole | ✅ | answered | 10 | 8 | 0 | 117 | 115 | 23.0 |
| H2-button | ✅ | answered | 5 | 3 | 0 | 69 | 68 | 23.1 |
| H2-edit-axial-hole | ✅ | answered | 18 | 16 | 0 | 171 | 167 | 22.9 |
| H2-edit-shaft-chamfer | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.2 |
| H2-edit-longer | ✅ | answered | 2 | 1 | 0 | 15 | 14 | 22.9 |
| H2-square-flange | ✅ | answered | 2 | 1 | 0 | 10 | 9 | 23.0 |

- **H2-plate-rounded-holes:** body 1: cylinder diameters [8.0] instead of [8.0, 20.0] mm

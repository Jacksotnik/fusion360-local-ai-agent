# h2-v8-r1

Модель `gemma4-12b:q8_0`, промпт `cad8`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H2-disk-square-hole | ✅ | answered | 2 | 1 | 0 | 14 | 13 | 23.4 |
| H2-block-axial-hole | ✅ | answered | 2 | 1 | 0 | 8 | 6 | 23.4 |
| H2-channel | ✅ | answered | 6 | 5 | 0 | 20 | 19 | 23.5 |
| H2-flanged-bushing | ✅ | answered | 2 | 1 | 0 | 9 | 8 | 23.4 |
| H2-plate-rounded-holes | ✅ | answered | 5 | 4 | 0 | 38 | 36 | 23.2 |
| H2-cube-chamfer-all | ✅ | answered | 2 | 1 | 0 | 6 | 5 | 23.4 |
| H2-pin-cross-hole | ✅ | max_calls | 20 | 20 | 0 | 236 | 231 | 23.0 |
| H2-button | ✅ | answered | 9 | 8 | 0 | 42 | 39 | 23.1 |
| H2-edit-axial-hole | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.2 |
| H2-edit-shaft-chamfer | ✅ | answered | 2 | 1 | 0 | 6 | 5 | 23.2 |
| H2-edit-longer | ✅ | answered | 3 | 4 | 0 | 61 | 59 | 23.0 |
| H2-square-flange | ✅ | answered | 2 | 1 | 0 | 10 | 9 | 23.0 |


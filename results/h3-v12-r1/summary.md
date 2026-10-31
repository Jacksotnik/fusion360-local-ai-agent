# h3-v12-r1

Модель `gemma4-12b:q8_0`, промпт `cad12`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H3-holes-row | ✅ | answered | 2 | 1 | 0 | 13 | 11 | 23.2 |
| H3-cyl-hex-hole | ✅ | answered | 4 | 3 | 0 | 45 | 42 | 23.1 |
| H3-box-shell | ✅ | answered | 2 | 1 | 0 | 7 | 5 | 23.4 |
| H3-angle-30 | ✅ | answered | 2 | 1 | 0 | 7 | 5 | 23.2 |
| H3-disk-chamfers | ✅ | answered | 2 | 1 | 0 | 8 | 6 | 23.3 |
| H3-counterbore | ✅ | answered | 2 | 1 | 0 | 10 | 7 | 23.3 |
| H3-stepped-shaft | ✅ | answered | 2 | 1 | 0 | 8 | 6 | 23.4 |
| H3-slot-45 | ✅ | answered | 3 | 2 | 0 | 15 | 13 | 23.2 |
| H3-edit-thicker-round | ✅ | answered | 4 | 3 | 0 | 32 | 29 | 23.2 |
| H3-edit-holes-chamfer | ❌ | answered | 2 | 1 | 0 | 11 | 8 | 23.2 |
| H3-edit-hub | ✅ | answered | 2 | 1 | 0 | 10 | 7 | 23.2 |
| H3-cube-3-holes | ✅ | answered | 2 | 1 | 0 | 12 | 9 | 23.1 |

- **H3-edit-holes-chamfer:** body 1: volume 6201.504 instead of 6237.109 mm3

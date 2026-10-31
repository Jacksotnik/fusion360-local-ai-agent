# h1-v11-r1

Модель `gemma4-12b:q8_0`, промпт `cad11`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H-ring | ✅ | answered | 2 | 1 | 0 | 8 | 6 | 23.3 |
| H-blind-hole | ✅ | answered | 2 | 1 | 0 | 9 | 7 | 23.4 |
| H-pin-chamfers | ✅ | answered | 2 | 1 | 0 | 7 | 5 | 23.3 |
| H-angle | ✅ | answered | 2 | 1 | 0 | 7 | 5 | 23.4 |
| H-hex | ✅ | answered | 5 | 4 | 0 | 71 | 68 | 23.2 |
| H-cup | ❌ | answered | 4 | 3 | 0 | 21 | 18 | 23.3 |
| H-slot-plate | ✅ | answered | 2 | 1 | 0 | 9 | 6 | 23.4 |
| H-hole-grid | ✅ | answered | 2 | 1 | 0 | 19 | 16 | 23.2 |
| H-shaft-step | ✅ | answered | 2 | 1 | 0 | 7 | 5 | 23.6 |
| H-edit-thicker | ✅ | answered | 3 | 2 | 0 | 7 | 5 | — |
| H-edit-boss | ✅ | answered | 2 | 1 | 0 | 10 | 8 | 23.4 |
| H-edit-round-all | ✅ | answered | 2 | 1 | 0 | 6 | 4 | — |

- **H-cup:** body 1: volume 21764.954 instead of 8629.955 mm3

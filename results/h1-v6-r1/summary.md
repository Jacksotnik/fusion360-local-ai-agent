# h1-v6-r1

Модель `gemma4-12b:q8_0`, промпт `cad6`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H-ring | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.3 |
| H-blind-hole | ✅ | answered | 2 | 1 | 0 | 8 | 7 | 23.2 |
| H-pin-chamfers | ✅ | answered | 3 | 2 | 0 | 12 | 10 | 23.2 |
| H-angle | ✅ | answered | 3 | 2 | 0 | 22 | 20 | 23.1 |
| H-hex | ✅ | answered | 6 | 5 | 0 | 76 | 75 | 23.1 |
| H-cup | ✅ | answered | 3 | 2 | 0 | 22 | 21 | 23.2 |
| H-slot-plate | ✅ | answered | 7 | 6 | 0 | 42 | 40 | 23.2 |
| H-hole-grid | ✅ | answered | 2 | 1 | 0 | 25 | 24 | 23.1 |
| H-shaft-step | ❌ | answered | 3 | 2 | 0 | 14 | 13 | 23.2 |
| H-edit-thicker | ✅ | answered | 3 | 2 | 0 | 7 | 5 | — |
| H-edit-boss | ✅ | answered | 2 | 1 | 0 | 9 | 7 | 23.2 |
| H-edit-round-all | ✅ | answered | 2 | 1 | 0 | 6 | 4 | — |

- **H-shaft-step:** body 1: volume 7099.999 instead of 6572.212 mm3

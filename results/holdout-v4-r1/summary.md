# holdout-v4-r1

Модель `gemma4-12b:q8_0`, промпт `cad`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| H-ring | ✅ | answered | 2 | 1 | 0 | 12 | 11 | 23.6 |
| H-blind-hole | ✅ | answered | 2 | 1 | 0 | 15 | 14 | 23.4 |
| H-pin-chamfers | ✅ | answered | 3 | 2 | 0 | 20 | 19 | 23.4 |
| H-angle | ✅ | answered | 3 | 2 | 0 | 233 | 232 | 23.0 |
| H-hex | ✅ | max_calls | 20 | 20 | 0 | 308 | 304 | 22.9 |
| H-cup | ✅ | answered | 3 | 2 | 0 | 43 | 42 | 22.9 |
| H-slot-plate | ✅ | answered | 3 | 2 | 0 | 20 | 19 | 22.9 |
| H-hole-grid | ✅ | answered | 2 | 1 | 0 | 23 | 22 | 22.9 |
| H-shaft-step | ✅ | answered | 2 | 1 | 0 | 29 | 28 | 23.0 |
| H-edit-thicker | ✅ | answered | 3 | 2 | 0 | 8 | 7 | 23.0 |
| H-edit-boss | ✅ | answered | 3 | 2 | 0 | 17 | 15 | 22.9 |
| H-edit-round-all | ✅ | answered | 3 | 2 | 0 | 8 | 6 | 23.2 |


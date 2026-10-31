# photo-v9-r1

Модель `gemma4-12b:q8_0`, промпт `cad9`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| P-plate-holes | ✅ | answered | 2 | 1 | 0 | 17 | 14 | 23.4 |
| P-flange-8 | ✅ | answered | 2 | 1 | 0 | 13 | 10 | 23.5 |
| P-angle-holes | ❌ | answered | 2 | 1 | 0 | 10 | 6 | 23.5 |
| P-box-open | ✅ | answered | 2 | 1 | 0 | 10 | 6 | 23.5 |
| P-shaft-steps | ✅ | answered | 2 | 1 | 0 | 9 | 6 | 23.5 |

- **P-angle-holes:** body 1: volume 7841.460 instead of 7684.381 mm3

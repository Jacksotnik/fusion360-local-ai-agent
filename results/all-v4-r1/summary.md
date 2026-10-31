# all-v4-r1

Модель `gemma4-12b:q8_0`, промпт `cad`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L1-cube | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.1 |
| L1-cylinder | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.3 |
| L1-plate | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.3 |
| L2-plate-center-hole | ✅ | answered | 2 | 1 | 0 | 8 | 7 | 23.2 |
| L2-plate-4-holes | ✅ | answered | 2 | 1 | 0 | 10 | 9 | 23.2 |
| L2-bushing | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.2 |
| L3-bigger-holes | ✅ | answered | 3 | 2 | 0 | 8 | 6 | 23.3 |
| L3-round-corners | ✅ | answered | 3 | 2 | 0 | 19 | 18 | 23.0 |
| L3-chamfer | ✅ | answered | 3 | 2 | 0 | 9 | 8 | 23.3 |
| L4-flange | ✅ | answered | 2 | 1 | 0 | 19 | 18 | 23.1 |
| L4-revolve-knob | ✅ | answered | 2 | 1 | 0 | 12 | 11 | 23.1 |


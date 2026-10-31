# all-v3-r1

Модель `gemma4-12b:q8_0`, промпт `cad`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L1-cube | ✅ | answered | 2 | 1 | 0 | 6 | 6 | 23.9 |
| L1-cylinder | ✅ | answered | 2 | 1 | 0 | 5 | 4 | 23.9 |
| L1-plate | ✅ | answered | 2 | 1 | 0 | 6 | 5 | 23.8 |
| L2-plate-center-hole | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.7 |
| L2-plate-4-holes | ✅ | answered | 2 | 1 | 0 | 14 | 13 | 23.6 |
| L2-bushing | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.6 |
| L3-bigger-holes | ✅ | answered | 3 | 2 | 0 | 7 | 6 | 23.6 |
| L3-round-corners | ✅ | answered | 4 | 3 | 0 | 28 | 26 | 23.5 |
| L3-chamfer | ✅ | answered | 3 | 2 | 0 | 9 | 8 | 23.6 |
| L4-flange | ✅ | answered | 2 | 1 | 0 | 16 | 15 | 23.3 |
| L4-revolve-knob | ✅ | answered | 2 | 1 | 0 | 12 | 11 | 23.4 |


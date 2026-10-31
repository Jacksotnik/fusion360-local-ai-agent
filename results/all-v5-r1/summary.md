# all-v5-r1

Модель `gemma4-12b:q8_0`, промпт `cad5`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L1-cube | ✅ | answered | 2 | 1 | 0 | 5 | 4 | 23.2 |
| L1-cylinder | ✅ | answered | 2 | 1 | 0 | 5 | 4 | 23.2 |
| L1-plate | ✅ | answered | 2 | 1 | 0 | 5 | 4 | 23.2 |
| L2-plate-center-hole | ✅ | answered | 2 | 1 | 0 | 7 | 6 | 23.1 |
| L2-plate-4-holes | ✅ | answered | 2 | 1 | 0 | 8 | 7 | 23.1 |
| L2-bushing | ✅ | answered | 2 | 1 | 0 | 6 | 5 | 23.1 |
| L3-bigger-holes | ✅ | answered | 2 | 1 | 0 | 7 | 5 | 23.1 |
| L3-round-corners | ❌ | answered | 2 | 1 | 0 | 6 | 4 | 23.3 |
| L3-chamfer | ✅ | answered | 2 | 1 | 0 | 6 | 5 | 23.1 |
| L4-flange | ✅ | answered | 11 | 10 | 0 | 113 | 109 | 22.9 |
| L4-revolve-knob | ✅ | answered | 3 | 2 | 0 | 42 | 41 | 23.0 |

- **L3-round-corners:** body 1: volume 10974.926 instead of 11892.699 mm3

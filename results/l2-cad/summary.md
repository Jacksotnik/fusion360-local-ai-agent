# l2-cad

Модель `gemma4-12b:q8_0`, промпт `cad`, функции CAD: True, think=False, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L2-plate-center-hole | ✅ | answered | 2 | 1 | 0 | 9 | 8 | 23.4 |
| L2-plate-4-holes | ✅ | answered | 2 | 1 | 0 | 14 | 13 | 23.3 |
| L2-bushing | ❌ | answered | 2 | 1 | 0 | 7 | 6 | 23.4 |

- **L2-bushing:** body 1: volume 4821.903 instead of 3534.292 mm3; body 1: cylinder diameters [10.0] instead of [10.0, 20.0] mm

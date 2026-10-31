# l5-v11-think4k-r1

Модель `gemma4-12b:q8_0`, промпт `cad11`, функции CAD: True, think=True, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L5-lid | ✅ | answered | 4 | 3 | 0 | 214 | 212 | 22.8 |
| L5-support | ✅ | answered | 2 | 1 | 0 | 78 | 76 | 23.0 |
| L5-bracket | ❌ | answered | 2 | 1 | 0 | 115 | 112 | 22.9 |
| L5-pulley | ✅ | answered | 2 | 1 | 0 | 69 | 66 | 22.9 |
| L5-housing | ✅ | answered | 10 | 9 | 0 | 531 | 525 | 22.6 |
| L5-clevis | ✅ | answered | 9 | 2 | 0 | 1241 | 1238 | 22.9 |

- **L5-bracket:** body 1: volume 11089.641 instead of 12376.881 mm3

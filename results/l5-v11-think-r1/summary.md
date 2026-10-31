# l5-v11-think-r1

Модель `gemma4-12b:q8_0`, промпт `cad11`, функции CAD: True, think=True, num_ctx 32768.

| Задача | Итог | Статус | Вызовов модели | Инструменты | Подталкиваний | Время, с | Из них модель, с | Генерация, т/с |
|---|---|---|---|---|---|---|---|---|
| L5-lid | ✅ | answered | 7 | 3 | 0 | 316 | 314 | 22.9 |
| L5-support | ✅ | answered | 2 | 1 | 0 | 50 | 47 | 22.9 |
| L5-bracket | ❌ | answered | 4 | 2 | 0 | 146 | 143 | 22.9 |
| L5-pulley | ✅ | answered | 8 | 1 | 0 | 370 | 368 | 22.8 |
| L5-housing | ✅ | answered | 2 | 1 | 0 | 64 | 61 | 22.9 |
| L5-clevis | ❌ | max_calls | 20 | 0 | 0 | 1060 | 1058 | 22.9 |

- **L5-bracket:** body 1: volume 11089.641 instead of 12376.881 mm3
- **L5-clevis:** bodies: 0 instead of 1

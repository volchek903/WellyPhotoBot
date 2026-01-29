# WellyPhotoBot

Telegram-бот для генерации фото с бонусами, рефералами и оплатой через ЮKassa.

## Возможности
- Приветственный бонус 1 генерация при первом запуске
- Генерация по 1–2 фото + текстовый промпт
- Баланс и списание генераций
- Реферальный бонус +2 генерации
- Покупка генераций через ЮKassa

## Быстрый старт
1) Создайте `.env` по образцу `.env.example`
2) Установите зависимости:
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
3) Запустите бота:
```
python -m app.main
```

## YooKassa (polling)
Оплата подтверждается через polling статусов платежей с интервалом,
который задаётся переменной `YOOKASSA_POLL_INTERVAL_SECONDS`.

## Примечания
- Kie AI использует загрузку файлов через File Stream Upload и задачи createTask/recordInfo.
- Для рефералов можно указать `REQUIRED_CHANNEL_ID` и `REQUIRED_CHANNEL_LINK`.

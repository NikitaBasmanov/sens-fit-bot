# SENS Fit Bot

Telegram бот для подбора бюстгальтера SENS Fit с использованием фото-скана или квиза.

## Функциональность

### Основные возможности:

-   **Фото-скан**: Анализ 2 фото (фронтальное + профильное) для точного определения размера
-   **Квиз без фото**: Подбор размера на основе ручных измерений
-   **Обратная связь**: Сбор отзывов о точности подбора
-   **Дополнительные команды**: `/help`, `/myfit`, `/reset`, `/privacy`

### Полный путь клиента:

1. **Приветствие** (`/start`)

    - Приветствие и согласие на продолжение

2. **Согласие на обработку данных**

    - Информация о хранении фото ≤ 24 ч
    - Согласие на 152-ФЗ / GDPR

3. **Выбор метода**

    - 📸 Фото-скан (точнее)
    - ✏️ Квиз без фото

4. **Фото-скан сценарий:**

    - Инструкции по съемке
    - Ввод роста
    - Загрузка фронтального фото
    - Загрузка профильного фото
    - Анализ (~5 сек)
    - Результат с рекомендацией

5. **Квиз сценарий:**

    - Ввод обхвата под грудью
    - Ввод обхвата груди
    - Выбор стиля
    - Выбор комфорта
    - Расчет размера

6. **Обратная связь**
    - ✅ Подошло / ❌ Не подошло

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone https://github.com/NikitaBasmanov/sens-fit-bot.git
cd sens-fit-bot
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Настройка переменных окружения

Создайте файл `.env` на основе `env_example.txt`:

```bash
cp env_example.txt .env
```

Отредактируйте `.env` файл, указав ваши значения:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=ваш_токен_бота

# Bodygram API Configuration
BODYGRAM_API_KEY=ваш_ключ_api
BODYGRAM_ORG_ID=ваш_org_id

# API URLs
BODYGRAM_API_URL=https://platform.bodygram.com/api/orgs/{ORG_ID}/scans

# Bot Settings
BOT_NAME=SENS Fit Bot
BOT_DESCRIPTION=Telegram bot for SENS Fit bra size fitting

# Contact Information
SUPPORT_EMAIL=support@sensfit.com
PRIVACY_EMAIL=privacy@sensfit.com

# Product Links
WILDBERRIES_BASE_URL=https://www.wildberries.ru/catalog/
OZON_BASE_URL=https://www.ozon.ru/product/

# Default Values
DEFAULT_AGE=25
DEFAULT_WEIGHT=60000
DEFAULT_GENDER=female
```

### 4. Запуск бота

```bash
python bot.py
```

## Структура проекта

```
sens-fit-bot/
├── bot.py              # Основной файл бота
├── requirements.txt    # Зависимости
├── README.md          # Документация
├── .env               # Переменные окружения (создается локально)
├── env_example.txt    # Пример файла переменных окружения
└── .gitignore         # Исключения для Git
```

## Переменные окружения

### Обязательные переменные:

-   `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота
-   `BODYGRAM_API_KEY` - ключ API Bodygram
-   `BODYGRAM_ORG_ID` - ID организации в Bodygram

### Опциональные переменные:

-   `BOT_NAME` - название бота (по умолчанию: "SENS Fit Bot")
-   `BOT_DESCRIPTION` - описание бота
-   `SUPPORT_EMAIL` - email поддержки
-   `PRIVACY_EMAIL` - email по вопросам конфиденциальности
-   `WILDBERRIES_BASE_URL` - базовый URL для ссылок на Wildberries
-   `OZON_BASE_URL` - базовый URL для ссылок на Ozon
-   `DEFAULT_AGE` - возраст по умолчанию (по умолчанию: 25)
-   `DEFAULT_WEIGHT` - вес по умолчанию в граммах (по умолчанию: 60000)
-   `DEFAULT_GENDER` - пол по умолчанию (по умолчанию: "female")

## Тестирование

### Мини-чек-лист для теста:

1. **Фото-скан путь:**

    - `/start` → «Да» → «Согласен» → «Фото-скан»
    - Ввести рост 170
    - Отправить 2 фото (можно заглушки)
    - Дождаться размера 75C
    - Получить ссылку на товар

2. **Квиз путь:**

    - `/start` → «Согласен» → «Квиз»
    - Заполнить мерки 78/92
    - Выбрать «Классический», «Комфорт»
    - Получить размер 80B и товар

3. **Дополнительные команды:**
    - `/myfit` → показать последнюю рекомендацию
    - `/reset` → сбросить данные
    - `/privacy` → политика конфиденциальности

## API Интеграция

Бот интегрирован с Bodygram API для анализа фото:

-   Отправка фото в base64 формате
-   Получение измерений тела
-   Расчет размера бюстгальтера

## Безопасность

-   Фото хранятся не более 24 часов
-   Соблюдение 152-ФЗ и GDPR
-   Данные используются только для подбора размера
-   Не передаются третьим лицам
-   Чувствительные данные хранятся в `.env` файле (не в репозитории)

## Разработка

### Добавление новых переменных окружения:

1. Добавьте переменную в `env_example.txt`
2. Добавьте загрузку в `bot.py`:
    ```python
    NEW_VARIABLE = os.getenv('NEW_VARIABLE', 'default_value')
    ```
3. Обновите документацию

### Локальная разработка:

```bash
# Создайте .env файл для разработки
cp env_example.txt .env

# Установите зависимости
pip install -r requirements.txt

# Запустите бота
python bot.py
```

## Поддержка

По вопросам работы бота: support@sensfit.com
По вопросам конфиденциальности: privacy@sensfit.com

# Memory Palace - Telegram Ads Search Bot

Telegram бот для поиска объявлений о продаже в групповых чатах Тбилиси. Использует AI для парсинга запросов и семантического поиска.

## Возможности

- Поиск объявлений о продаже в Telegram чатах
- Обработка запросов на естественном языке
- Уточняющие вопросы для неопределённых запросов
- Семантический поиск с использованием OpenAI embeddings
- Кэширование индексации (не чаще 1 раза в час для одних чатов)

## Требования

- Python 3.11+
- Docker и Docker Compose
- Telegram Bot Token
- Telegram API credentials (API ID, API Hash)
- OpenAI API Key

## Установка и запуск

> Все команды выполняются из корневой директории проекта `memory-palace/`

### 1. Клонируйте репозиторий

```bash
git clone <repository-url>
cd memory-palace
```

### 2. Создайте виртуальное окружение

```bash
# Из корня проекта memory-palace/
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установите зависимости

```bash
# Из корня проекта memory-palace/
pip install -r requirements.txt
```

### 4. Настройте переменные окружения

```bash
# Из корня проекта memory-palace/
cp .env.example .env
```

Отредактируйте `.env` файл:

```env
# Telegram Bot
BOT_TOKEN=your_bot_token_from_botfather

# Telegram Userbot (получите на https://my.telegram.org)
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+995xxxxxxxxx

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/memory_palace

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small
```

### 5. Запустите PostgreSQL

```bash
# Из корня проекта memory-palace/
docker compose up -d
```

### 6. Примените миграции базы данных

```bash
# Из корня проекта memory-palace/
alembic upgrade head
```

### 7. Запустите бота

```bash
# Из корня проекта memory-palace/
python main.py
```

При первом запуске потребуется авторизация в Telegram через телефон и код подтверждения.

## Использование

### Примеры запросов

- "Найди мне чемодан"
- "Ищу велосипед за последние 2 недели"
- "Продаётся ли iPhone в @tbilisi_baraholka?"
- "Нужна детская коляска"

### Команды бота

- `/start` - Приветствие и инструкции
- `/help` - Справка по использованию
- `/clear` - Очистить историю диалога

## Конфигурация чатов

Список чатов для поиска настраивается в файле `config/chats.yaml`.

### Способы указания чатов

Чаты можно указывать двумя способами:

1. **По username** - простой способ, работает для публичных чатов:
   ```yaml
   - username: baraholka_tbi
     name: "Барахолка Тбилиси"
   ```

2. **По ID чата** - более надёжный способ, работает для любых чатов:
   ```yaml
   - id: -1001234567890
     name: "Приватный чат"
   ```

3. **Оба варианта** - если указаны оба, используется ID (более надёжно):
   ```yaml
   - username: baraholka_tbi
     id: -1001234567890
     name: "Барахолка Тбилиси"
   ```

### Как узнать ID чата

1. Добавьте бота `@userinfobot` или `@getidsbot` в нужный чат
2. Бот отправит ID чата (обычно начинается с `-100` для супергрупп)
3. Или используйте Telegram Web: откройте чат и скопируйте ID из URL

### Пример конфигурации

```yaml
default_chats:
  - username: baraholka_tbi
    name: "Барахолка Тбилиси"
  - username: tbilisi_sell_buy
    id: -1001234567890  # Опционально - более надёжно
    name: "Купи-Продай Тбилиси"
  - id: -1009876543210  # Только ID для приватного чата
    name: "Приватная группа"

settings:
  default_days: 7
  max_days: 30
  index_cache_minutes: 60
```

### Указание чатов в запросах

Пользователи также могут указывать чаты в запросах:
- По username: "Найди чемодан в @baraholka_tbi"
- По ID: "Найди чемодан в -1001234567890"

## Автоматическая очистка данных

База данных автоматически очищает сообщения старше 30 дней с помощью расширения `pg_cron`.

- **Расписание**: каждую ночь в 03:00 UTC
- **Что удаляется**: сообщения с датой публикации старше 30 дней
- **Дополнительно**: корректируется `indexed_from_date` в статусе индексации

### Ручной запуск очистки

При необходимости можно запустить очистку вручную:

```bash
docker compose exec postgres psql -U postgres -d memory_palace -c "SELECT cleanup_old_messages();"
```

### Просмотр запланированных задач

```bash
docker compose exec postgres psql -U postgres -d memory_palace -c "SELECT * FROM cron.job;"
```

## Деплой на Digital Ocean

### Требования для сервера

- Ubuntu 22.04 LTS
- Минимум 1 GB RAM (рекомендуется 2 GB)
- 25 GB SSD
- Файл `userbot.session` (создаётся при первой локальной авторизации)

### 1. Создание Droplet

1. Войдите в [Digital Ocean](https://cloud.digitalocean.com/)
2. Create → Droplets
3. Выберите:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic, $6/mo (1 GB RAM) или $12/mo (2 GB RAM)
   - **Region**: Frankfurt или Amsterdam (ближе к Telegram серверам)
   - **Authentication**: SSH Key (рекомендуется)
4. Create Droplet

### 2. Настройка сервера

Подключитесь к серверу:

```bash
ssh root@your_droplet_ip
```

Установите Docker:

```bash
# Обновление системы
apt update && apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com | sh

# Добавление пользователя в группу docker (опционально)
usermod -aG docker $USER

# Проверка установки
docker --version
docker compose version
```

Настройте firewall:

```bash
ufw allow OpenSSH
ufw allow 443/tcp  # Если планируете HTTPS
ufw enable
```

### 3. Деплой приложения

Клонируйте репозиторий:

```bash
cd /opt
git clone <repository-url> memory-palace
cd memory-palace
```

Скопируйте файлы с локальной машины (выполните на локальном компьютере):

```bash
# Session файл (ВАЖНО: без него бот не сможет индексировать чаты)
scp userbot.session root@your_droplet_ip:/opt/memory-palace/

# .env файл
scp .env root@your_droplet_ip:/opt/memory-palace/
```

Или создайте `.env` на сервере:

```bash
nano /opt/memory-palace/.env
```

```env
# Telegram Bot
BOT_TOKEN=your_bot_token

# Telegram Userbot
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=+995xxxxxxxxx

# PostgreSQL (ВАЖНО: используйте надёжный пароль!)
POSTGRES_DB=memory_palace
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here

# OpenAI
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small
```

### 4. Запуск

```bash
cd /opt/memory-palace

# Сборка и запуск контейнеров
docker compose -f docker-compose.prod.yml up -d --build

# Проверка статуса
docker compose -f docker-compose.prod.yml ps

# Применение миграций
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

### 5. Управление

**Просмотр логов:**

```bash
# Все сервисы
docker compose -f docker-compose.prod.yml logs -f

# Только приложение
docker compose -f docker-compose.prod.yml logs -f app

# Последние 100 строк
docker compose -f docker-compose.prod.yml logs --tail=100 app
```

**Перезапуск:**

```bash
docker compose -f docker-compose.prod.yml restart app
```

**Остановка:**

```bash
docker compose -f docker-compose.prod.yml down
```

**Обновление приложения:**

```bash
cd /opt/memory-palace
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### 6. Мониторинг

Проверка состояния контейнеров:

```bash
docker compose -f docker-compose.prod.yml ps
```

Использование ресурсов:

```bash
docker stats
```

Проверка cron-задач очистки:

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d memory_palace -c "SELECT * FROM cron.job;"
```

### Troubleshooting

**Бот не отвечает:**

```bash
# Проверьте логи
docker compose -f docker-compose.prod.yml logs app

# Убедитесь, что контейнер запущен
docker compose -f docker-compose.prod.yml ps
```

**Ошибка авторизации Telethon:**

Session файл должен быть создан локально перед деплоем. Если нужно создать заново:

```bash
# Остановите контейнер
docker compose -f docker-compose.prod.yml down

# Удалите старый session
rm userbot.session

# Создайте новый локально и скопируйте на сервер
```

**База данных недоступна:**

```bash
# Проверьте статус PostgreSQL
docker compose -f docker-compose.prod.yml logs postgres

# Проверьте, что healthcheck проходит
docker compose -f docker-compose.prod.yml ps
```

## Архитектура

```
memory-palace/
├── src/
│   ├── bot/           # Telegram Bot (aiogram)
│   ├── indexer/       # Telethon userbot для индексации
│   ├── database/      # SQLAlchemy модели и репозитории
│   ├── ai/            # OpenAI интеграция (parser, agent, embeddings)
│   └── config.py      # Конфигурация
├── config/
│   └── chats.yaml     # Список чатов
├── alembic/           # Миграции БД
└── tests/             # Тесты
```

## Тестирование

```bash
# Из корня проекта memory-palace/
pytest tests/ -v
```

## Лицензия

MIT

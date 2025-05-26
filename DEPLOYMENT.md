# Развертывание Telegram Q&A бота в Google Cloud Run

Это руководство поможет вам развернуть Telegram Q&A бот в Google Cloud Run для обеспечения стабильной работы в режиме webhook.

## Предварительные требования

1. Аккаунт Google Cloud Platform
2. Установленный и настроенный Google Cloud SDK
3. Установленный Docker
4. Токен вашего Telegram бота

## Шаг 1: Подготовка проекта

1. Создайте файл `Dockerfile` в корневой директории проекта:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

2. Создайте файл `.dockerignore`:

```
__pycache__/
*.py[cod]
*$py.class
*.so
.env
.env.local
.venv
env/
venv/
ENV/
backups/
*.db
```

3. Обновите файл `requirements.txt`:

```
python-telegram-bot==20.8
python-dotenv==1.1.0
```

4. Настройте переменные окружения в файле `.env`:

```
TELEGRAM_TOKEN=your_bot_token
CHANNEL_ID=@your_channel_id
ADMIN_GROUP_ID=-1001234567890
ADMIN_IDS=123456789,987654321
BOT_MODE=webhook
WEBHOOK_URL=https://your-project-id.run.app
PORT=8080
```

## Шаг 2: Создание проекта в Google Cloud

1. Создайте новый проект в Google Cloud Console или используйте существующий:

```bash
gcloud projects create your-project-id --name="Telegram QA Bot"
gcloud config set project your-project-id
```

2. Активируйте необходимые API:

```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
```

## Шаг 3: Сборка и публикация Docker-образа

1. Соберите Docker-образ:

```bash
docker build -t gcr.io/your-project-id/telegram-qa-bot .
```

2. Настройте Docker для работы с Google Container Registry:

```bash
gcloud auth configure-docker
```

3. Отправьте образ в Container Registry:

```bash
docker push gcr.io/your-project-id/telegram-qa-bot
```

## Шаг 4: Развертывание в Cloud Run

1. Разверните приложение в Cloud Run:

```bash
gcloud run deploy telegram-qa-bot \
  --image gcr.io/your-project-id/telegram-qa-bot \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="TELEGRAM_TOKEN=your_bot_token,CHANNEL_ID=@your_channel_id,ADMIN_GROUP_ID=-1001234567890,ADMIN_IDS=123456789,BOT_MODE=webhook,PORT=8080"
```

2. Получите URL вашего сервиса:

```bash
gcloud run services describe telegram-qa-bot --platform managed --region us-central1 --format="value(status.url)"
```

## Шаг 5: Настройка Webhook

1. Обновите переменную `WEBHOOK_URL` в Cloud Run с полученным URL:

```bash
gcloud run services update telegram-qa-bot \
  --platform managed \
  --region us-central1 \
  --set-env-vars="WEBHOOK_URL=https://your-service-url"
```

2. Перезапустите сервис для применения изменений.

## Шаг 6: Проверка работоспособности

1. Проверьте логи сервиса:

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=telegram-qa-bot" --limit 10
```

2. Отправьте сообщение боту и убедитесь, что он отвечает.

## Дополнительные настройки

### Настройка базы данных

Для продакшен-среды рекомендуется использовать Cloud SQL вместо локальной SQLite базы данных:

1. Создайте экземпляр Cloud SQL:

```bash
gcloud sql instances create telegram-qa-bot-db \
  --database-version=POSTGRES_13 \
  --tier=db-f1-micro \
  --region=us-central1
```

2. Создайте базу данных:

```bash
gcloud sql databases create qabot --instance=telegram-qa-bot-db
```

3. Создайте пользователя:

```bash
gcloud sql users create qabot --instance=telegram-qa-bot-db --password=your-secure-password
```

4. Обновите код бота для работы с PostgreSQL вместо SQLite.

### Настройка автоматического резервного копирования

1. Настройте автоматическое резервное копирование для Cloud SQL:

```bash
gcloud sql instances patch telegram-qa-bot-db \
  --backup-start-time=23:00 \
  --enable-bin-log
```

## Устранение неполадок

### Бот не отвечает

1. Проверьте логи сервиса:

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=telegram-qa-bot" --limit 50
```

2. Убедитесь, что webhook настроен правильно:

```bash
curl -X GET "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

3. Проверьте, что все переменные окружения установлены правильно:

```bash
gcloud run services describe telegram-qa-bot --platform managed --region us-central1
```

### Ошибки при развертывании

1. Проверьте логи сборки:

```bash
gcloud builds list
```

2. Проверьте логи конкретной сборки:

```bash
gcloud builds log BUILD_ID
```

## Мониторинг и обслуживание

1. Настройте оповещения о состоянии сервиса:

```bash
gcloud alpha monitoring channels create \
  --display-name="Telegram Bot Alerts" \
  --type=email \
  --channel-labels=email_address=your-email@example.com
```

2. Настройте политику оповещений:

```bash
gcloud alpha monitoring policies create \
  --display-name="Telegram Bot Down" \
  --condition-filter="metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"telegram-qa-bot\" metric.label.\"response_code\"=\"500\" AND metric.label.\"response_code\"=\"502\" AND metric.label.\"response_code\"=\"503\" AND metric.label.\"response_code\"=\"504\"" \
  --condition-threshold-value=1 \
  --condition-threshold-duration=60s \
  --notification-channels=CHANNEL_ID
```

## Заключение

Теперь ваш Telegram Q&A бот развернут в Google Cloud Run и работает в режиме webhook. Это обеспечивает стабильную работу и масштабируемость вашего бота.

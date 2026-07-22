# Платёжный сервис с провайдером-симулятором

Сервис для проведения платёжных операций через внешнего провайдера с гарантией идемпотентности, устойчивостью к сетевым сбоям и восстановлением после перезапусков.

## Оглавление

- [Требования](#требования)
- [Конфигурация](#конфигурация)
- [API](#api)
  - [Проверка здоровья](#проверка-здоровья)
  - [Создание операции](#создание-операции)
  - [Отправка операции](#отправка-операции)
  - [Получение состояния](#получение-состояния)
  - [История событий](#история-событий)
  - [Callback-квитанция](#callback-квитанция)
- [Сквозной сценарий](#сквозной-сценарий)
- [Тестирование](#тестирование)
- [Структура проекта](#структура-проекта)

---

## Требования

- Docker и Docker Compose (установленные)
- Порт `8080` свободен для сервиса-кандидата
- Порт `8081` свободен для симулятора провайдера

---

## Конфигурация

Переменные окружения задаются через файл `.env`:

| Переменная | Описание |
|------------|----------|
| `PROVIDER_URL` | Адрес внешнего провайдера |
| `DB_HOST` | Хост базы данных PostgreSQL |
| `DB_PORT` | Порт базы данных PostgreSQL |
| `DB_USER` | Пользователь базы данных PostgreSQL |
| `DB_PASS` | Пароль пользователя базы данных PostgreSQL |
| `DB_NAME` | Имя базы данных PostgreSQL |

**Настройка окружения:**

Скопируйте `.env.example` в `.env` и заполните переменные актуальными значениями для вашего окружения. 
Для запуска тестов используется `.test.env` с аналогичной структурой.

---

## API

### Проверка готовности
```http
GET /health
```
Ответ:
```json
{ "status": "ok" }
```
---
### Создание операции
```http
POST /operations/
Content-Type: application/json
```
Тело запроса:

```json
{
  "operationId": "op-123",
  "amount": "1000.00",
  "currency": "RUB",
  "description": "Оплата заказа"
}
```
Успешный ответ: 201 Created
```json
{
  "operationId": "op-123",
  "amount": "1000.00",
  "currency": "RUB",
  "description": "Оплата заказа",
  "status": "CREATED",
  "providerPaymentId": null,
  "createdAt": "2026-07-22T12:00:00Z",
  "updatedAt": "2026-07-22T12:00:00Z"
}
```
Ошибка: 409 Conflict - операция с таким operationId уже существует.

---
### Отправка операции
```http
POST /operations/{id}/submit
```
Если операция в статусе CREATED - переводит в PROCESSING, возвращает 202 Accepted и запускает фоновую отправку провайдеру.

Если операция уже PROCESSING, COMPLETED или REJECTED - возвращает текущее состояние с 200 OK (идемпотентно).

Успешный ответ (первый submit): 202 Accepted

```json
{
  "operationId": "op-123",
  "amount": "1000.00",
  "currency": "RUB",
  "description": "Оплата заказа",
  "status": "PROCESSING",
  "providerPaymentId": null,
  "createdAt": "2026-07-22T12:00:00Z",
  "updatedAt": "2026-07-22T12:00:01Z"
}
```
Повторный submit: 200 OK (то же тело, статус может быть PROCESSING или финальным).

---
### Получение состояния
```http
GET /operations/{id}
```
Ответ: 200 OK

```json
{
  "operationId": "op-123",
  "amount": "1000.00",
  "currency": "RUB",
  "description": "Оплата заказа",
  "status": "COMPLETED",
  "providerPaymentId": "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
  "createdAt": "2026-07-22T12:00:00Z",
  "updatedAt": "2026-07-22T12:00:02Z"
}
```

---
### История событий
```http
GET /operations/{id}/events
```
Ответ: 200 OK
```json
[
  {
    "eventId": 1,
    "type": "CREATED",
    "operationId": "op-123",
    "providerPaymentId": null,
    "fromStatus": null,
    "toStatus": "CREATED",
    "message": "Operation created",
    "occurredAt": "2026-07-22T12:00:00Z"
  },
  {
    "eventId": 2,
    "type": "PROCESSING",
    "operationId": "op-123",
    "providerPaymentId": null,
    "fromStatus": "CREATED",
    "toStatus": "PROCESSING",
    "message": "Change status from CREATED to PROCESSING.",
    "occurredAt": "2026-07-22T12:00:01Z"
  },
  {
    "eventId": 3,
    "type": "PROVIDER_RESPONSE",
    "operationId": "op-123",
    "providerPaymentId": "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
    "fromStatus": "PROCESSING",
    "toStatus": "PROCESSING",
    "message": "Added provider payment id.",
    "occurredAt": "2026-07-22T12:00:01Z"
  },
  {
    "eventId": 4,
    "type": "COMPLETED",
    "operationId": "op-123",
    "providerPaymentId": "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
    "fromStatus": "PROCESSING",
    "toStatus": "COMPLETED",
    "message": "Status changed to COMPLETED via receipt",
    "occurredAt": "2026-07-22T12:00:02Z"
  }
]
```

---
### Callback-квитанция
Симулятор провайдера отправляет квитанцию на этот эндпоинт:

```http
POST /receipts
Content-Type: application/json
```
Тело запроса:
```json
{
  "providerPaymentId": "aa5b7856-e9f2-4fd5-955b-38b1f28d9c57",
  "operationId": "op-123",
  "result": "COMPLETED",
  "message": "Payment completed",
  "occurredAt": "2026-07-22T12:00:02Z"
}
```
Успешный ответ: 204 No Content

Возможные ошибки:

- 404 Not Found - операция не найдена

- 409 Conflict - несовпадающий providerPaymentId (если уже установлен другой)

---
### Сквозной сценарий
Создание операции

```bash
curl -X POST http://localhost:8080/operations/ \
     -H "Content-Type: application/json" \
     -d '{"operationId":"op-123","amount":"1000.00","currency":"RUB","description":"Test"}'
```
Ожидаем статус CREATED.

Отправка

```bash
curl -X POST http://localhost:8080/operations/op-123/submit
```
Получаем 202 Accepted, статус становится PROCESSING.

Провайдер обрабатывает запрос - симулятор автоматически отправит callback на /receipts.

Проверка статуса

```bash
curl http://localhost:8080/operations/op-123
```
Через некоторое время статус станет COMPLETED или REJECTED.

Просмотр истории

```bash
curl http://localhost:8080/operations/op-123/events
```
---
## Тестирование

Были написаны тесты для проверки функциональности. Тесты разделены на две группы:
- **Основные тесты** - проверка API, CRUD-операций и валидации (не используют фоновые задачи).
- **Тесты с фоновыми задачами** - проверка конкурентности, ошибок провайдера и восстановления после перезапуска (требуют изолированного окружения).

Тесты с фоновыми задачами требуют изолированного запуска из-за асинхронных конфликтов.

---

## Структура проекта

```
.
├── docker-compose.yml
├── Dockerfile
├── README.md
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
├── src/
│   ├── main.py                 # FastAPI приложение
│   ├── api/                    # HTTP-эндпоинты
│   │   ├── health.py
│   │   ├── operations.py
│   │   └── receipts.py
│   ├── core/                   # Конфигурация, БД, исключения, FSM
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── exceptions.py
│   │   └── state_machine.py
│   ├── db/                     # Работа с данными
│   │   ├── models/             # SQLAlchemy-модели
│   │   ├── schemas/            # Pydantic-схемы
│   │   └── crud/               # Операции с БД
│   └── services/               # Внешние вызовы
│       └── provider.py
└── tests/                      # Тесты
    ├── test_api.py
    ├── test_crud.py
    ├── test_validation.py
    └── with_background_tasks/  # Тесты с фоновыми задачами
        ├── test_concurrency.py
        ├── test_provider_errors.py
        └── test_recovery.py
```

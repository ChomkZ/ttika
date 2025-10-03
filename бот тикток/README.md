# 🚀 TikTok Automation System

**Полная автоматизация TikTok через iPhone подключенный к компьютеру**

Система автоматизации для загрузки контента в TikTok с поддержкой каруселей (циклическая загрузка и удаление видео) и AI-генерации английских хештегов для дейтинга.

## 🎯 Особенности

### ✨ Основной функционал
- **iOS Automation**: Управление iPhone через Appium (без jailbreak)
- **Carousel Logic**: Автоматические циклы загрузки 6 видео → ожидание 40-60 мин → удаление → повтор
- **AI Hashtags**: Генерация английских хештегов для дейтинг-контента с использованием ИИ
- **Multi-Account**: Поддержка множественных TikTok аккаунтов
- **VPN Management**: Управление OVPN подключениями на iPhone
- **Web Dashboard**: Современный интерфейс управления

### 🛠 Технические возможности
- Автоматическая загрузка существующих видео
- Генерация уникальных описаний с хештегами
- Мониторинг статусов и логирование
- Планировщик задач и очереди
- Скриншоты и отладка устройства

## 🏗️ Архитектура

```
TikTok Automation System
├── Backend (FastAPI + MongoDB)
│   ├── iOS Automation Engine (Appium)
│   ├── Hashtag Generator (AI)
│   ├── Video & Account Management
│   └── Carousel Controller
├── Frontend (React Dashboard)
│   ├── Device Management Interface
│   ├── Video Library Manager
│   ├── Hashtag Generation Tools
│   └── Real-time Monitoring
└── Database (MongoDB)
    ├── TikTok Accounts
    ├── Video Files & Metadata
    ├── Hashtag Templates
    └── Carousel Sessions
```

## 🚀 Быстрый старт

### Предварительные требования
1. **iPhone с iOS 14+** подключенный по USB
2. **Appium Server** установленный на компьютере
3. **WebDriverAgent** настроенный для iOS (без jailbreak)
4. **TikTok app** установленный на iPhone

### Запуск системы
```bash
# Все сервисы уже запущены
sudo supervisorctl status

# Проверка API
curl http://localhost:8001/api/

# Доступ к dashboard
http://localhost:3000
```

## 📱 Настройка iOS Automation

### 1. Установка Appium
```bash
# Установка Appium Server
npm install -g appium@next
appium driver install xcuitest

# Запуск Appium (в отдельном терминале)
appium --port 4723
```

### 2. Настройка WebDriverAgent
1. Откройте проект WebDriverAgent в Xcode
2. Настройте signing с вашим Apple Developer ID
3. Установите на iPhone через Xcode
4. Доверьте приложению в Настройки > Основные > VPN и управление устройством

### 3. Подключение iPhone
1. Подключите iPhone по USB
2. Разрешите доверие компьютеру
3. В dashboard нажмите "Connect iPhone"

## 🎠 Использование Carousel (Карусели)

### Создание карусели
1. **TikTok Accounts** → Добавить аккаунт(ы)
2. **Videos** → Загрузить видео
3. **Carousel** → Create Carousel:
   - Выбрать аккаунт
   - Выбрать видео  
   - Настроить количество загрузок (по умолчанию 6)
   - Время ожидания (40-60 минут)
   - Количество циклов

### Логика работы карусели
```
Цикл карусели:
┌─────────────────────────────────────────┐
│ 1. Загрузить 6 одинаковых видео        │
│    └─ С уникальными хештегами для каждого│
│                                         │
│ 2. Ждать 40-60 минут для набора просмотров│
│                                         │
│ 3. Удалить все 6 видео                 │
│                                         │
│ 4. Повторить цикл (если авто-рестарт)   │
└─────────────────────────────────────────┘
```

## 🏷️ Генерация хештегов

### AI-генерация
- **Тематика**: Английские хештеги для дейтинга
- **Целевая аудитория**: Англоговорящие пользователи
- **Примеры**: `#dating #love #single #relationship #datenight #romance #flirt #crush #match #attraction`

## 🎯 Результат

✅ **Полная автоматизация TikTok** через iPhone без jailbreak  
✅ **Carousel система** с циклами загрузки и удаления  
✅ **AI-генерация хештегов** на английском для дейтинга  
✅ **Мультиаккаунтность** с переключением между профилями  
✅ **VPN управление** для безопасности  
✅ **Современный Dashboard** для полного контроля  

**Система готова к использованию для автоматизации TikTok контента!** 🚀

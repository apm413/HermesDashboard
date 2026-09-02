# HermesDashboard — Steampunk-обвязка для агентов HermeSvideo и tier1

Панель мониторинга двух студий автоматизации владельца.
Один dashboard, два проекта, реальный live-стрим из логов.

**Дизайн:** **Cyberscope Neon** (выбран из 5 вариантов).
Неоновый циан #00FFE0 на глубоком тёмно-синем #050810, марширующие
пунктирные рёбра в DAG, скан-линии по ячейкам, латунные мотивы сведены
к минимуму — акцент на голограммной эстетике.

---

## Что внутри

| Компонент | Назначение |
|-----------|-----------|
| **DAG-граф** | Узлы = агенты (HermeSvideo: 5 шт, tier1: 5 шт), рёбра = поток данных |
| **Лог-стрим** | Live-вывод stdout/stderr агентов с задержкой ≤1 сек |
| **Connected-панель** | Проверки подключений: RunPod, ComfyUI, Ollama, Reddit, Twitter, Telegram, ElevenLabs |
| **Бюджет** | HermesV2: $3/день, $45/мес. Tier1: $0 (Ollama локально). Манометры. |
| **Управление** | Кнопки Run-now (tier1), Terminate pod (HermeSvideo) |
| **Фильтр** | По статусу: все / ошибки / готово / ожидание |

### v2.0 — новые фичи (апгрейд после ресёрча GitHub-плагинов)

| Фича | Где | Что взято |
|------|-----|-----------|
| **Theme switcher** (cyan / amber / fuchsia) | header | Свой стиль — конкуренты предлагали только тёмную/светлую |
| **Filter + search** в лог-стриме | над логами | `Kori-x/hermes-dashboard` — search по агенту/сообщению |
| **System metrics** (CPU/RAM/Disk) через psutil | между header и logs | `duan78/hermes-dashboard` — добавил live-gauges |
| **Token / cost counter** с daily chart | под budget-манометром | `duan78` — парсинг `input=N output=N cost=$X.XX` из логов |
| **Agent phase tracker** (PROC/DONE/WAIT/ERR pill) | на running-узлах DAG | Свой паттерн — Kori-x показывал только idle/done |
| **Action buttons** → реальные команды | toolbar | `p-matrix/hermes-monitor` — Run now / Terminate pod → subprocess + RunPod API |
| **Browser notifications** | (отключены по умолчанию) | Заготовка для алертов (errors / budget exceeded) |

---

## Быстрый старт (standalone)

```bash
# 1) Создай venv с правильными версиями (FastAPI 0.110 + Starlette 0.36)
cd "C:/Users/CarlosRi/HermesDashboard"
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 2) Запусти backend (uvicorn)
start.bat                  # Windows
# или
./start.sh                 # Linux/Mac

# 3) Открой в браузере
# http://127.0.0.1:5557/
```

Сразу увидишь:

- DAG-граф с узлами **infra-agent → character-agent → video-agent → post-prod → publish-agent** (HermeSvideo)
- DAG-граф с узлами **schedule → seo-curator / reddit-poster / twitter-poster → analytics** (tier1)
- Живой лог-стрим событий из реальных `.log` файлов обоих проектов
- Манометры бюджета и панель подключений
- Кнопки `Run-now seo / reddit / twitter / analytics` в тулбаре

---

##Установка как Hermes-плагин

```bash
hermes plugins install "C:/Users/CarlosRi/HermesDashboard"
hermes plugins enable hermes-dashboard
```

Плагин зарегистрирован в обоих режимах:

- **Web dashboard** (`~/.hermes/plugins/hermes-dashboard/dashboard/`) — `manifest.json` + `plugin_api.py` + `dist/`
- **Desktop Electron** (`~/.hermes/desktop-plugins/hermes-dashboard/plugin.js`) — вкладка `/hermes-dashboard`

Открой вкладку **Hermes Dashboard** в браузере или desktop-приложении.

---

## 🖥️ Десктоп-приложение (Electron)

Отдельное окно с иконкой на рабочем столе. Слева — dashboard, справа — **встроенный чат** для общения с агентами.

### Установка

```bash
# 1) Запусти install.bat (один раз)
install.bat

# Что делает:
#   ✓ Создаёт .venv для backend
#   ✓ Устанавливает Electron + electron-builder (npm)
#   ✓ Создаёт ярлык "Hermes Dashboard" на рабочем столе

# 2) Запусти с рабочего стола (двойной клик по иконке)
#    или вручную:
start.bat
```

### Скриншот

*(после `npm install` — здесь будет скриншот Electron-окна)*

### Чат-команды

Введи в правой панели (с префиксом `/` или без):

| Команда | Что делает |
|---------|-----------|
| `/help` | Список всех команд |
| `/tier1:once` | Прогнать все tier1-агенты разом (mock) |
| `/tier1:seo` `/tier1:reddit` `/tier1:twitter` `/tier1:analytics` | Запустить отдельный tier1-агент |
| `/video:demo` | Сгенерировать демо-сценарий HermeSvideo |
| `/video:status` | Проверить состояние ключей/бюджета |
| `/video:verify-keys` | Проверить API-ключи |
| `/video:test-all` | Smoke-тест всех video-агентов |
| `/budget` | Показать дневной/месячный бюджет |
| `/system` | CPU/RAM/Disk |
| `/logs` | Последние строки из .log файлов |
| `просто текст` | Свободный ввод (эхо) |

Автокомплит по `Tab` (например, набери `/t` → `Tab` → `/tier1:twitter`). История — стрелками `↑`/`↓`.

### Сборка portable .exe (Windows)

```bash
cd app
npm run build:win
# → app/dist-app/HermesDashboard-2.0.0-portable.exe (~150 MB)
```

Portable-версия — single-file, не требует установки, кладётся на флешку.

---

## Дизайн-варианты

При создании было предложено 5 вариантов (`screenshots/variants/`):

| Файл | Название | Акцент |
|------|----------|--------|
| v1-neomechanicum.css | Neomechanicum 2099 | Базовая латунь + неон + пар (из промта) |
| v2-chrono-atelier.css | Chrono-Atelier | Викторианский циферблат, без неона |
| v3-cyberscope-neon.css | **Cyberscope Neon** ✅ | Голограмма, основной яркий циан |
| v4-anatomical-engine.css | Anatomical Engine | Чертёжная тема, пунктир + скошенные углы |
| v5-foundry-furnace.css | Foundry Furnace | Кузнечный цех, оранжевый неон + медь |

**Чтобы переключиться на другой вариант:**

```bash
cp screenshots/variants/v2-chrono-atelier.css dashboard/dist/style.css
# перезапустить backend
```

`comparison.html` показывает все 5 рядом: <http://127.0.0.1:5557/comparison.html>

---

## Архитектура

```
HermeSvideo/logs/*.log  ──┐
                          │
tier1-fresh/logs/studio/  ──┤──> LogTailerHub ──> SQLite (state.db)
                          │              │
                          │              └──> WebSocket ──> Frontend
                          │
                          └──> parsers/hermesvideo.py  ──> событие {ts, agent, level, message, status, scenario_id}
                              parsers/tier1.py        ──┘

Frontend (vanilla React):
  DAGCanvas    ── ручной SVG с steampunk-обвязкой (без xyflow)
  LogStream    ── real-time лента
  ConnectedPanel ── live probes каждые 5 сек
  BudgetPanel  ── манометры HermesV2 ($3/день) + tier1 ($0)
  BrassGear, ValveLamp, SteamPipe, Manometer ── SVG-компоненты
```

### Технологии

- **Backend:** FastAPI 0.110 + Starlette 0.36 + httpx (probe'ы) + SQLite
- **Frontend:** React 18 (UMD), ручной SVG (без сторонних UI-китов), WebSocket
- **Без сборки:** `dist/index.js` работает как IIFE, без webpack/vite

### Конфигурация через env

| Переменная | Дефолт | Назначение |
|------------|--------|-----------|
| `HERMES_VIDEO_ROOT` | `~/HermeSvideo` | Путь к проекту HermeSvideo |
| `TIER1_ROOT` | `~/Desktop/tier1-fresh` | Путь к tier1 |
| `HERMES_DASHBOARD_DB` | `~/.hermes/plugins/hermes-dashboard/state.db` | SQLite |
| `HERMES_PORT` | 5557 | Порт backend |

---

## Что было сделано vs не сделано

### Готово
- Real-time лог-стрим из реальных `.log` файлов (HermeSvideo + tier1)
- DAG-граф с автоматическим определением статуса узлов
- 5 дизайн-вариантов с переключением через `comparison.html` / `preview.html`
- WebSocket broadcast с историей последних 50 событий
- Active-probe каждые 5 сек: RunPod, ComfyUI, Ollama, Reddit, Twitter, Telegram, ElevenLabs
- Бюджет HermesV2: парсинг `common.py` для лимитов + чтение spend-логов
- Кнопки Run-now / Terminate pod / Set-active project
- Фильтры по статусу (errors/done/waiting)
- Мобильный адаптивный layout (CSS `@media (max-width: 900px)`)
- Маскирование секретов (`rpa_***`, `Bearer ***`)
- Hermes-плагин manifest + plugin.yaml + desktop/plugin.js

### Не готово (mock или недоступно)
- **Hermes web-server в этой системе сломан** (FastAPI 0.115 ↔ Starlette 1.3 несовместимость в `web_server.py`) — вкладка в desktop-приложении через `web_server` НЕ появится, пока Hermes не обновит web_server. Standalone через `start.bat` работает полностью.
- **В HermeSvideo demo** падает `Path.home()` если нет env-переменной `HOME`/`USERPROFILE` — это баг его `common.py`, не моего плагина. Мой код ловит ошибку gracefully и продолжает работать.
- **xyflow** не использован — он требует npm-сборку, не подходит для Hermes plugin-runtime-shim. DAG реализован ручным SVG (150 строк), что даёт полный контроль над стилем и нулевой bundle-size.

---

## Известные ограничения

1. **Headless Chrome в скриншотах** показывает фрейм device (`mobile.html`/`tablet.html`), но фон не отрисовался в первый момент. Решение — `shoot.py` через Chrome headless с `--window-size` (см. `shoot.py`).
2. **Tier1 logs путь**: `tier1/config.py` пишет в `PROJECT_ROOT.parent / logs / studio = Desktop/logs/studio`. Логика автодетекта в `log_tailer.py` это обрабатывает.
3. **HermeSvideo dry-run** без `RunPod` ключей делает мок-рендер (цветные клипы). Real-режим требует API-ключей в `.env`.

---

## Лицензия

MIT
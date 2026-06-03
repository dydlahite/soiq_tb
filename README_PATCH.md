# Soiqweqq site patch

Готовый статический патч сайта по приложенному макету и ассетам.

## Что внутри

- `site/index.html` - главная страница.
- `site/assets/css/styles.css` - весь визуал: фон, шапка, hero, плеер, about, галерея, чат.
- `site/assets/js/site.js` - лёгкая интерактивность: sticky header, modal gallery, mock chat, кнопка плеера.
- `site/assets/images/` - обработанные изображения из архива: фон, аватар, кот, логотип, галерея.

## Как запустить локально

Открой `site/index.html` в браузере.

Нормальный вариант через локальный сервер:

```bash
cd site
python3 -m http.server 8080
```

Потом открыть:

```text
http://localhost:8080
```

## Куда класть в проект

Вариант без боли:

```bash
cp -r site /root/bot/site
```

Или положить папку `site` в корень репозитория и деплоить как обычную статику.

## Что заменить перед публикацией

В `site/index.html` наверху есть конфиг:

```html
<script>
  window.SOIQWEQQ_CONFIG = {
    telegramBotUrl: 'https://t.me/soiqweqq_bot',
    chatEndpoint: ''
  };
</script>
```

- `telegramBotUrl` - ссылка на реального Telegram-бота.
- `chatEndpoint` - URL веб-API для общения на сайте. Пока пусто, поэтому чат работает как демо.

Ожидаемый формат API для `chatEndpoint`:

```http
POST /your-chat-endpoint
Content-Type: application/json

{"message":"текст пользователя"}
```

Ответ:

```json
{"reply":"ответ бота"}
```

## Примечания

- Никаких внешних CDN и npm-зависимостей нет. Да, сайт может жить без священного `node_modules`, страшно представить.
- Фон и галерея сделаны из приложенных изображений.
- Макет не вставлен как картинка, а пересобран нормальной HTML/CSS-структурой.
- Верстка адаптивная: desktop/tablet/mobile.

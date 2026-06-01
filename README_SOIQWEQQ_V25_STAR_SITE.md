# Soiqweqq v25 star site

Что изменено:

- верхний логотип, плеер и меню закреплены сверху при прокрутке;
- вместо гирлянды добавлены звезды, луны, кометы, орбиты и скопления звезд;
- верхний логотип использует новый лунный аватар `web/assets/logo_moon.png`, имя остается сбоку;
- вернулась подпись `/ digital shadow` над `Soiqweqq`;
- кнопки получили иконки: Telegram для запуска бота и сердце для запуска чата на сайте;
- чат можно двигать за верхнюю панель на ПК;
- в чат добавлена кнопка разворота `□`;
- в шапке чата вместо сердечка стоит аватар с лунным логотипом и звездной меткой;
- индикатор `печатает...` вынесен в шапку чата;
- время сообщений закреплено в правом нижнем углу пузыря;
- переносы строк в сообщениях сохраняются;
- скроллбары в чате стали тонкими и приглушенными;
- блок `Обо мне` выровнен;
- фотографии увеличены и растянуты шире по сайту.

## Что загрузить в GitHub

```text
app_api.py
site_track.txt
web/index.html
web/chat.html
web/style.css
web/app.js
web/assets/logo_moon.png
web/assets/soiqweqq_clean_layer_hero.webp
web/assets/soiqweqq_clean_layer_hero.png
web/assets/about_photos/about_1.jpg
web/assets/about_photos/about_2.jpg
web/assets/about_photos/about_3.jpg
web/assets/about_photos/about_4.jpg
web/assets/about_photos/about_5.jpg
web/assets/about_photos/about_6.jpg
web/assets/about_photos/about_7.jpg
web/assets/about_photos/about_8.jpg
web/assets/about_photos/about_9.jpg
```

## Что можно удалить

```text
web/assets/garland_top.png
web/assets/garland_left.png
web/assets/garland_right.png
web/assets/garland_parts/
web/assets/soiqweqq_final_mockup.jpg
web/assets/soiqweqq_final_mockup.webp
web/assets/tv_cat.jpg
web/v20_override.css
```

## После загрузки

```bash
cd /root/bot
git pull
python3 -m py_compile app_api.py
systemctl restart soiq-api
systemctl status soiq-api --no-pager -l
```

Открывать с пробиванием кэша:

```text
https://soiqweqq.ddns.net/?v=25
```

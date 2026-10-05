# mech-from-code

**Боевой мех, город, машины и 43 секунды кино со взрывами в Blender, сделанные целиком из Python-кода ИИ-агентами за один вечер.**
Автор задач не владеет 3D и не написал ни строки кода: 7 агентов (Claude Code), около 6,5 часа.

> Статус: промежуточный результат. До идеала далеко, но за вечер с нуля — шикарно.

## Видео

- Кино (46 с): https://youtu.be/-im47qmBRSw
- Как это сделано (3 мин): https://youtu.be/YLClGyeYqjM
- Shorts: https://youtube.com/shorts/uRMU2hI8g8Q

## Скачать

**[mech-from-code-v1.0.0.zip](https://github.com/sergeyramas/mech-from-code/releases/latest)** (6.8 МБ) лежит в Releases. Внутри:

| | |
|---|---|
| `GUIDE.md` | Как повторить самому без знаний 3D: установка, запуск Blender без окна, этапы, грабли |
| `PROMPTS.md` | Готовые промпты для Claude Code на каждый этап |
| `mech.blend` | Робот v3.1, около 245 тыс. треугольников, около 215 деталей |
| `scripts/` | Python-скрипты Blender (робот, окружение, машины, кино), звука и монтажа |

## Цифры

7 агентов · 0 строк кода от человека · 245 тыс. треугольников · 1027 кадров · рендер 62 мин на Mac (EEVEE) · 220 обломков здания.

## Стек

Blender 5.2 (bpy, bmesh, EEVEE, rigid body) · Claude Code · Python (numpy, scipy, Pillow) · ElevenLabs (SFX, музыка, озвучка) · HyperFrames · ffmpeg.

## Ссылки

- Telegram «Рамас. Лаборатория»: https://t.me/ramas_lab
- Карточка проекта: https://sergeyramas.vercel.app/projects/mech-from-code

Скрипты публикуются как есть, для изучения и повторения. Ключей API в репозитории нет: ключ ElevenLabs передаётся через переменную окружения `ELEVENLABS_API_KEY`.

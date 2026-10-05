# Changelog

Формат по [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии по [SemVer](https://semver.org/lang/ru/).

## [1.0.0] — 2026-10-05

### Добавлено
- `GUIDE.md`: как повторить проект без знаний 3D, по этапам: робот → сверка силуэта (IoU) → окружение → машины → кино (fracture, rigid body, bullet-time) → звук → монтаж.
- `PROMPTS.md`: готовые промпты для Claude Code на каждый этап.
- `mech.blend`: модель робота v3.1 (около 245 тыс. треугольников, процедурные материалы).
- `scripts/blender/`: скрипты робота, сверки силуэта, окружения (`env/`), машин (`vehicles/`) и кино (`cine/`).
- `scripts/sound/`: синтез звука кодом, сведение по `events.json`, шаблон генерации SFX через ElevenLabs (ключ из переменной окружения).
- `scripts/video/`: генерация HyperFrames-композиций, сведение голоса, обложка.

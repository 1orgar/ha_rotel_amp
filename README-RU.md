<p align="center">
  <img src="https://raw.githubusercontent.com/1orgar/ha_rotel_amp/main/brand/logo@2x.png" alt="Rotel Amp" height="96">
</p>

# Rotel Amplifier (TCP) для Home Assistant

🇬🇧 [English version](https://github.com/1orgar/ha_rotel_amp/blob/main/README.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/1orgar/ha_rotel_amp/actions/workflows/validate.yml/badge.svg)](https://github.com/1orgar/ha_rotel_amp/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/1orgar/ha_rotel_amp)](https://github.com/1orgar/ha_rotel_amp/releases)
[![License](https://img.shields.io/github/license/1orgar/ha_rotel_amp)](https://github.com/1orgar/ha_rotel_amp/blob/main/LICENSE)

Локальное управление усилителями Rotel (RA-1572, RA-1572MKII и другими моделями с тем же TCP-протоколом) по сети, через порт 9590.
Основано на [k4Mr3/Rotel-RA-1572](https://github.com/k4Mr3/Rotel-RA-1572) и переписано под современный Home Assistant.

## Возможности
- **Настройка через UI** (config flow), YAML не нужен.
- **Только нужные входы.** Отметьте входы, которыми пользуетесь, — в списке источников будут только они.
- **Свои названия входов**, например `Coax 2` → `Стример`. Меняются в любой момент через «Настроить».
- **Ограничение максимальной громкости.**
- **Автоматический реконнект:** после перезагрузки или отключения питания усилителя интеграция подключается сама, перезапускать HA не нужно.
- **Актуальное состояние:**
  - сразу после подключения или переподключения запрашивается всё состояние;
  - каждые N секунд (по умолчанию 30) запрашиваются питание, громкость, mute и вход; каждый 10-й опрос запрашивает всё состояние;
  - при выходе усилителя из standby автоматически запрашивается всё состояние.
- **Связанный media player для каждого входа** (заменяет настройку через `universal`, см. ниже).
- **Следование за воспроизведением:** когда связанный плеер начинает играть, усилитель включается, переключается на его вход и ставит другие плееры на паузу.
- **Автовыключение** через N минут без воспроизведения.
- Изменения, сделанные на передней панели или пультом, приходят мгновенно (push).
- Сервисы для тембров, баланса, колонок A/B, диммера, bypass и класса PC-USB.

## Установка

### HACS
1. HACS → ⋮ → *Custom repositories* → `https://github.com/1orgar/ha_rotel_amp`, тип *Integration*.
2. Найдите **Rotel Amplifier (TCP)**, установите и перезапустите Home Assistant.

### Вручную
Скопируйте `custom_components/rotel_amp` в `<config>/custom_components/` и перезапустите HA.

## Настройка
На усилителе установите **POWER OPTION = Quick**, иначе в standby он недоступен по сети.

*Настройки → Устройства и службы → Добавить интеграцию → Rotel Amplifier (TCP)*:

1. Хост, порт (по умолчанию `9590`), название.
2. Используемые входы, максимальная громкость, интервал опроса (`0` — отключить опрос), автовыключение (`0` — выключено).
3. Названия входов и, при желании, связанный media player для каждого входа с опцией «переключаться на этот вход».

Всё это можно изменить позже кнопкой **«Настроить»**.

## Связанные плееры
К каждому входу можно привязать другой `media_player`, например стример, умную колонку или Chromecast, подключённые к этому входу. Пока выбран этот вход и усилитель включён, плеер Rotel работает как один общий плеер:

| | откуда |
|---|---|
| питание, громкость, mute, список и выбор входа | **усилитель** |
| состояние (`playing` / `paused` / `idle`), трек, исполнитель, альбом, обложка, позиция, приложение | **связанный плеер** |
| play / pause / stop / next / previous / перемотка / shuffle / repeat / play media / обзор медиа | передаются **связанному плееру** |

Доступные кнопки зависят от возможностей связанного плеера. Если у текущего входа нет связанного плеера или он недоступен, entity работает как обычный усилитель: состояние `on`, команды воспроизведения идут на сам усилитель (USB/Bluetooth). Какой плеер сейчас активен, показывает атрибут `linked_player`.

Это заменяет ручную настройку через `universal`:

```yaml
media_player:
  - platform: universal
    children: [media_player.gostinaia, media_player.yandex_station_xxx]
    active_child_template: >-
      {% if is_state_attr('media_player.rotel_amplifier', 'source', 'Алиса') %} ...
    commands: { select_source: ..., turn_on: ..., turn_off: ... }
    attributes: { volume_level: media_player.rotel_amplifier|volume_level, ... }
```

В интеграции достаточно в **«Настроить»** привязать *Алиса → media_player.yandex_station_xxx* и *Плеер → media_player.gostinaia*.

### Переключение на вход, когда плеер начинает играть
У каждого связанного плеера есть опция **«переключаться на этот вход, когда плеер начинает играть»**. Когда такой плеер начинает играть (его состояние становится `playing`):

1. Если усилитель выключен, он включается.
2. Если выбран другой вход, усилитель переключается на вход этого плеера.
3. Все остальные связанные плееры, которые сейчас играют, ставятся на паузу (или останавливаются, если паузу не поддерживают).

Например, вы включаете музыку на Яндекс Станции: усилитель включается и переключается на *Алису*. Потом запускаете стрим на другом плеере: усилитель переключается на *Плеер*, а Станция встаёт на паузу.

## Автовыключение
**Автовыключение, мин** (`0` — выключено) выключает усилитель, если он включён и ничего не играет заданное время. «Играет» значит, что связанный плеер текущего входа в состоянии `playing`. На входах без связанного плеера ничего не считается играющим, поэтому таймер идёт всё время, пока усилитель включён. Таймер запускается заново при каждой остановке воспроизведения и сбрасывается, как только что-то начинает играть или усилитель выключают.

## Сервисы
| Сервис | Параметры |
|---|---|
| `rotel_amp.set_bass` / `set_treble` | `level` −10…10 |
| `rotel_amp.set_balance` | `level` −15…15 (минус — влево) |
| `rotel_amp.set_dimmer` | `level` 0…6 |
| `rotel_amp.set_bypass` | `bypass` |
| `rotel_amp.set_speaker_a` / `set_speaker_b` | `enabled` |
| `rotel_amp.set_pcusb_class` | `usb_class` `1` / `2` |
| `rotel_amp.toggle_speaker_a/b`, `toggle_dimmer`, `bass_up/down`, `treble_up/down`, `balance_left/right` | — |
| `rotel_amp.get_current_status` | — (принудительно запросить всё состояние) |

Значения тембров, баланса и других параметров доступны в атрибутах entity.

## Отладка
```yaml
logger:
  logs:
    custom_components.rotel_amp: debug
```

## Разработка
```bash
pip install -r requirements_test.txt
ruff check custom_components tests
pytest
```
Тесты используют эмулятор усилителя: проверяются перезагрузка, «молчащий» усилитель, запуск при выключенном усилителе и опрос.

### Релизы
Версия берётся из `custom_components/rotel_amp/manifest.json`. При пуше в `main` с новой версией workflow **Tag & release** создаёт тег `v<version>` и GitHub Release с `rotel_amp.zip`.

## Лицензия
Apache-2.0. Rotel — торговая марка её владельца. Проект не связан с Rotel; иконка — обобщённая ручка громкости.

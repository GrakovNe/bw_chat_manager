# BW Chat Manager

Telegram moderation bot for the BW residential-complex chat: it keeps in the chat only those
messages that mention a building or courtyard from the list of allowed words. Everything else it
deletes, writes the reason into the chat and sends a report to the administrators.

## Quick start

```bash
make venv        # creates .venv and installs dependencies
cp .env.example .env   # fill in TELEGRAM_TOKEN
make run
```

## Configuration

All settings come from environment variables (the `.env` file is picked up automatically).
The full list with comments is in [.env.example](.env.example).

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `TELEGRAM_TOKEN` | yes | — | token from @BotFather |
| `MIN_LENGTH` | no | `10` | shorter messages are neither checked nor deleted |
| `ADMIN_IDS` | no | empty | administrator ids, comma-separated |
| `DATA_DIR` | no | `data` | directory with state files |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` |
| `ON_DELETE_REPLY` and other texts | no | in `config.py` | replies to users |
| `DUP_WINDOW_DAYS` | no | `7` | how many days to remember kept messages |
| `DUP_THRESHOLD` | no | `0.9` | similarity threshold from 0 to 1 |

In setting texts a line break is written as the `\n` sequence: `.env` and systemd
`EnvironmentFile` cannot hold multiline values.

A word may consist of several words: `/add building 3` adds "building 3" as a whole,
`/delete_word building 3` removes it.

The bot will not start without `TELEGRAM_TOKEN` and without the `data/bw_buildings.txt` file.
If the word list is empty, every message longer than `MIN_LENGTH` will be deleted; this is
reported in the log at startup.

## Data

| File | What it stores | In git |
| --- | --- | --- |
| `data/bw_buildings.txt` | allowed words, one per line, case-insensitive | yes |
| `data/chat_settings.json` | silent mode per chat | no |
| `data/recent_posts.json` | recent kept messages used to find repeats | no |

Writes are atomic (temporary file + `os.replace`), so an interrupted process leaves no half result.

A corrupt JSON does not stop the bot: `recent_posts.json` is rewritten from scratch on the first
write, `chat_settings.json` is read as empty (silent mode off everywhere), and the first `/silent`
command restores the file. The reason is always in the log.

## Bot commands

| Command | Who can | What it does |
| --- | --- | --- |
| `/add <word>` | bot administrator | adds a word to the list |
| `/delete_word <word>` | bot administrator | removes a word from the list |
| `/list_words` | bot administrator | shows the list (a long one over several messages) |
| `/silent on\|off` | any member | turns the bot's deletion replies in this chat off/on |
| `/start` | everyone | help |

## Repeats

If the same author in the same chat posts something similar more often than once every
`DUP_WINDOW_DAYS` days, the administrators get a report with a "Delete" button. The bot itself does
not delete the repeat: silently wiping ads based on a similarity metric is dangerous, the decision
is left to a human.

- Similarity is computed on the normalized text: case, punctuation, emoji and spaces do not matter,
  digits do — building 3 and building 5 are different ads.
- A repeat is a match above `DUP_THRESHOLD`; the percentage is shown in the report so the
  administrator can see the metric's confidence.
- Only messages from the same author in the same chat are compared, and only kept ones: deleted
  messages, replies and texts shorter than `MIN_LENGTH` do not go into memory.
- The window and threshold are shared across all chats; the memory lives in
  `data/recent_posts.json`: stale entries are dropped on every write and once more at bot startup.
- The beginning of the text is compared — the first 600 characters of the normalized message.
  A copy of an ad is recognizable from its beginning, while a full comparison of a many-page post
  would slow down the processing of the whole chat.
- The report goes to the same place as the deletion report: chat, author, text, the age of the
  match and the similarity percentage. Only a bot administrator can press "Delete".
- A long text in the report is truncated so the message fits Telegram's limit (4096 characters);
  otherwise the report would not be sent at all.
- After deletion the button disappears and a "🗑 Deleted by administrator `<nick>`" note appears
  under the report. If Telegram refuses, the button stays so the attempt can be repeated.

## BAN button

When the bot deletes a message, the administrators get a report "Deleted in chat `<chat_id>` from
`<nick>`: `<text>`" with a **BAN** button. Pressing it bans the author in the chat the message came
from: Telegram throws them out, and they return only if unbanned.

- Only a bot administrator from `ADMIN_IDS` can press it. Someone else's press is ignored, and the
  one who pressed gets "This command is available to administrators only."
- After a successful ban the report is rewritten: a "⛔ Banned by administrator `<nick>`" note
  appears and the button is removed — you cannot press the same report twice.
- If Telegram refused (not enough rights), the report stays with the button and the reason for the
  refusal is sent to the administrator: once the rights are fixed, press again.
- If the message could not be deleted, the administrators still find out: they receive "Failed to
  delete message `<id>` in chat `<chat_id>`: `<reason>`." A silently skipped message is worse than a
  visible error.
- Messages from the report's recipients (administrators) are not offered with a button at all, and a
  press on an old button left on a report from before this rule is rejected.
- There is no button when the author could not be determined — an anonymous channel post has no
  author and there is no one to ban.

The bot-administrator of the chat needs the "Ban users" right. The list of banned users lives in
Telegram, not in the bot's files — there is no ban registry of its own.

## How it is built

```
src/bwbot/
  config.py        settings from the environment
  moderation.py    pure decide() function — no dependency on Telegram
  callbacks.py     format of the BAN and "Delete" button callback_data and their parsing
  dedupe.py        text normalization, similarity and the repeat window
  storage/         state files: words, chat settings
  services/        logic on top of the repositories, works with the narrow ChatApi interface
  handlers/        thin telegram wrapper, only data is pulled out of Update
  telegram_api.py  ChatApi over telegram.Bot
  deps.py          dependency assembly
  app.py           Application assembly
```

Layer rule: `moderation.py` and `storage/` know nothing about Telegram, `services/` know only the
`ChatApi` protocol. The real `Bot` appears only in `handlers/` and `telegram_api.py`. That is why
all the logic is testable without the network.

## Development

```bash
make test    # pytest
make lint    # ruff check
make fmt     # ruff format + ruff check --fix
```

### How to add a new moderation rule

1. In `moderation.py` — a new `Action` and a branch in `decide()` (a pure function, tests right away).
2. In `services/moderation.py` — what to do with this `Action` (delete / mute / warn).
3. The reply text — in `config.py` + an environment variable.

"""The reel inbox: a private Telegram bot that saves the reels shared to it.

Share a reel from Instagram to the bot's chat and it lands in the motion
library's references (see ``motion_library.references``). The API starts the
bot on startup and stops it on shutdown (``running_in_background``); without
``TELEGRAM_BOT_TOKEN`` it does not start.

It long-polls Telegram, so it needs no public URL. Telegram allows one poller
per bot: run a single API process, or the others log a conflict and wait.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx

from core.config import get_settings
from core.logging_config import get_logger
from motion_library.references import ReelError, reel_link, save_reel

log = get_logger(__name__)

API_URL = "https://api.telegram.org/bot{token}/{method}"
# Telegram holds the request open this long when there is nothing new.
LONG_POLL_SECONDS = 50
RETRY_SECONDS = 10


class TelegramError(Exception):
    """A Telegram call failed. Never carries the request URL, which holds the bot token."""


async def _call(client: httpx.AsyncClient, method: str, **params: Any) -> Any:
    url = API_URL.format(token=get_settings().TELEGRAM_BOT_TOKEN, method=method)
    try:
        payload = (await client.post(url, json=params)).json()
    except (httpx.HTTPError, ValueError) as exc:
        raise TelegramError(f"{method}: {type(exc).__name__}") from None
    if not payload.get("ok"):
        raise TelegramError(f"{method}: {payload.get('description', 'refused')}")
    return payload["result"]


def _allowed_chats() -> set[str]:
    return {chat.strip() for chat in get_settings().TELEGRAM_ALLOWED_CHAT_IDS.split(",") if chat.strip()}


async def _answer(message: dict[str, Any]) -> str | None:
    """What to reply to a message, saving its reel on the way; None to stay silent."""
    chat = str((message.get("chat") or {}).get("id", ""))
    allowed = _allowed_chats()
    if not allowed:
        return f"This bot is not set up yet. Set TELEGRAM_ALLOWED_CHAT_IDS={chat} on the backend and restart it."
    if chat not in allowed:
        return None
    link = reel_link(message.get("text") or message.get("caption") or "")
    if link is None:
        return "Share an Instagram reel with me and I will save it to the motion library."
    try:
        reference = await save_reel(link)
    except ReelError as exc:
        return str(exc)
    except Exception as exc:  # one broken reel must not stop the inbox
        log.error(f"Reel inbox crashed on a reel: {type(exc).__name__}", exc_info=True)
        return "Something went wrong saving that reel."
    return f"Saved as {reference.id}." if reference.new else f"Already saved as {reference.id}."


async def run() -> None:
    offset = 0
    async with httpx.AsyncClient(timeout=LONG_POLL_SECONDS + 10) as client:
        while True:
            try:
                updates = await _call(
                    client, "getUpdates", offset=offset, timeout=LONG_POLL_SECONDS, allowed_updates=["message"],
                )
            except TelegramError as exc:
                log.warning(f"Reel inbox could not reach Telegram: {exc}")
                await asyncio.sleep(RETRY_SECONDS)
                continue
            for update in updates:
                # Telegram forgets an update once a later offset is asked for, so one
                # cut off by a shutdown is delivered again on the next start.
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                reply = await _answer(message)
                if reply is None:
                    continue
                try:
                    await _call(client, "sendMessage", chat_id=message["chat"]["id"], text=reply)
                except TelegramError as exc:
                    log.warning(f"Reel inbox could not reply: {exc}")


@asynccontextmanager
async def running_in_background() -> AsyncIterator[None]:
    """Run the inbox in the current event loop while the context is open."""
    if not get_settings().TELEGRAM_BOT_TOKEN:
        yield
        return
    task = asyncio.create_task(run())
    log.info("Reel inbox started")
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

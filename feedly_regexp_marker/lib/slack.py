import asyncio
import os
from functools import partial
from pathlib import Path
from typing import Callable, Optional

from feedly.api_client.utils import UnauthorizedAPIError
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp


async def poll_file_change(file_path: Path, interval_sec: float):
    def get_st_mtime() -> Optional[float]:
        return file_path.stat().st_mtime if file_path.exists() else None

    st_mtime = get_st_mtime()

    while get_st_mtime() == st_mtime:
        await asyncio.sleep(interval_sec)


async def write_token(ack, say, command, access_token_path: Path):
    await ack()

    # TODO: text の mrkdwn 形式から plain_text 形式への変換をちゃんとやる
    # NOTE: https://api.slack.com/reference/surfaces/formatting
    access_token = command["text"].strip("<>").strip()

    access_token_path.parent.mkdir(exist_ok=True, parents=True)
    access_token_path.write_text(access_token)

    await say(f"Token updated!: {access_token}")


def manage_access_token_using_slack(
    access_token_path: Path,
    slack_channel: str,
    slack_bot_token: str = os.environ["SLACK_BOT_TOKEN"],
    slack_app_token: str = os.environ["SLACK_APP_TOKEN"],
    polling_interval_sec: float = 10,
):
    def _wrapper1(f: Callable):
        async def _wrapper2(*args, **kwarg):
            app = AsyncApp(token=slack_bot_token)
            app.command("/update-token")(
                partial(write_token, access_token_path=access_token_path)
            )
            handler = AsyncSocketModeHandler(app, slack_app_token)

            slack_bot = asyncio.create_task(handler.start_async())

            while True:
                try:
                    v = f(*args, **kwarg)
                    break
                except UnauthorizedAPIError as e:
                    await app.client.chat_postMessage(
                        channel=slack_channel,
                        text=f"An error has occured: {e}",
                    )

                    await poll_file_change(
                        file_path=access_token_path,
                        interval_sec=polling_interval_sec,
                    )

            await slack_bot
            return v

        return _wrapper2

    return _wrapper1

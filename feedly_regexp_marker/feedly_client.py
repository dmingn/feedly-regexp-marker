from __future__ import annotations

from typing import Literal, Optional

from feedly.api_client.session import Auth, FeedlySession
from pydantic import BaseModel, ConfigDict

StreamId = str
EntryId = str
Action = Literal["markAsSaved", "markAsRead"]


class EntryContent(BaseModel):
    content: str
    model_config = ConfigDict(frozen=True)


class EntryOrigin(BaseModel):
    streamId: StreamId
    title: Optional[str] = None
    model_config = ConfigDict(frozen=True)


class Entry(BaseModel):
    """https://developer.feedly.com/v3/entries/#get-the-content-of-an-entry"""

    id: EntryId
    title: Optional[str] = None
    content: Optional[EntryContent] = None
    summary: Optional[EntryContent] = None
    origin: Optional[EntryOrigin] = None
    model_config = ConfigDict(frozen=True)


class StreamContents(BaseModel):
    """https://developers.feedly.com/v3/streams/#get-the-content-of-a-stream"""

    items: list[Entry]
    continuation: Optional[str] = None
    model_config = ConfigDict(frozen=True)


class FeedlyClient:
    def __init__(self, auth: Auth) -> None:
        self.session = FeedlySession(auth=auth)

    def fetch_unread_entries(self, continuation: str | None) -> list[Entry]:
        stream_contents = StreamContents.model_validate(
            self.session.do_api_request(
                relative_url="/v3/streams/contents",
                params=(
                    {
                        "streamId": f"user/{self.session.user.id}/category/global.all",
                        "count": "1000",
                        "ranked": "oldest",
                        "unreadOnly": "true",
                    }
                    | ({"continuation": continuation} if continuation else dict())
                ),
            )
        )

        if stream_contents.continuation:
            return stream_contents.items + self.fetch_unread_entries(
                continuation=stream_contents.continuation
            )
        else:
            return stream_contents.items

    def fetch_all_unread_entries(self) -> list[Entry]:
        return self.fetch_unread_entries(continuation=None)

    def mark_entries(self, entries: list[Entry], action: Action, dry_run: bool) -> None:
        if dry_run:
            print([entry.title for entry in entries])
            return

        if not entries:
            return

        self.session.do_api_request(
            relative_url="/v3/markers",
            data={
                "action": action,
                "type": "entries",
                "entryIds": [entry.id for entry in entries],
            },
        )

    def save_entries(self, entries: list[Entry], dry_run: bool) -> None:
        self.mark_entries(entries=entries, action="markAsSaved", dry_run=dry_run)

    def read_entries(self, entries: list[Entry], dry_run: bool) -> None:
        self.mark_entries(entries=entries, action="markAsRead", dry_run=dry_run)

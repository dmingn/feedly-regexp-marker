from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from feedly.api_client.session import FeedlySession


stream_id_t = str
entry_id_t = str
action_t = Literal["markAsSaved", "markAsRead"]


@dataclass(frozen=True)
class EntryContent:
    content: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntryContent:
        return cls(content=data["content"])


@dataclass(frozen=True)
class EntryOrigin:
    stream_id: stream_id_t
    title: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntryOrigin:
        return cls(
            stream_id=data["streamId"],
            title=data["title"],
        )


@dataclass(frozen=True)
class Entry:
    """https://developer.feedly.com/v3/entries/#get-the-content-of-an-entry"""

    id: entry_id_t
    title: Optional[str] = None
    content: Optional[EntryContent] = None
    origin: Optional[EntryOrigin] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entry:
        return cls(
            id=data["id"],
            title=data.get("title", None),
            content=EntryContent.from_dict(data["content"])
            if "content" in data
            else None,
            origin=EntryOrigin.from_dict(data["origin"])
            if "origin" in data
            else None,
        )


@dataclass(frozen=True)
class StreamContents:
    """https://developers.feedly.com/v3/streams/#get-the-content-of-a-stream"""

    items: list[Entry]
    continuation: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamContents:
        return cls(
            items=[Entry.from_dict(item) for item in data["items"]],
            continuation=data.get("continuation", None),
        )


class FeedlyController:
    def __init__(self) -> None:
        self.session = FeedlySession()
        self.continuation: Optional[str] = None

    def fetch_unread_entries(self, count: int = 1000) -> list[Entry]:
        stream_contents = StreamContents.from_dict(
            self.session.do_api_request(
                relative_url="/v3/streams/contents",
                params=(
                    {
                        "streamId": f"user/{self.session.user.id}/category/global.all",
                        "count": f"{count}",
                        "ranked": "oldest",
                        "unreadOnly": "true",
                    }
                    | (
                        {"continuation": self.continuation}
                        if self.continuation
                        else dict()
                    )
                ),
            )
        )

        self.continuation = stream_contents.continuation or self.continuation

        return stream_contents.items

    def __mark_entries(
        self, entries: list[Entry], action: action_t, dry_run: bool
    ) -> None:
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
        self.__mark_entries(
            entries=entries, action="markAsSaved", dry_run=dry_run
        )

    def read_entries(self, entries: list[Entry], dry_run: bool) -> None:
        self.__mark_entries(
            entries=entries, action="markAsRead", dry_run=dry_run
        )

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, RootModel
from pydantic_yaml import parse_yaml_file_as

from feedly_regexp_marker.feedly_controller import Action, StreamId
from feedly_regexp_marker.pattern_texts import PatternTexts


class EntryPatternTexts(BaseModel):
    title: PatternTexts = PatternTexts()
    content: PatternTexts = PatternTexts()
    model_config = ConfigDict(frozen=True)


class Rule(BaseModel):
    stream_ids: frozenset[StreamId]
    actions: frozenset[Action]
    patterns: EntryPatternTexts
    name: Optional[str] = None
    model_config = ConfigDict(frozen=True)


class Rules(RootModel[frozenset[Rule]]):
    model_config = ConfigDict(frozen=True)

    def __iter__(self):
        yield from self.root.__iter__()

    def __or__(self, other: Rules) -> Rules:
        return Rules(root=self.root | other.root)

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> Rules:
        return parse_yaml_file_as(cls, yaml_path)

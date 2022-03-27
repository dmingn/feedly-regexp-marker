from __future__ import annotations

import re
from pathlib import Path
from re import Pattern
from typing import Literal, Optional, TypeVar, cast, overload

from pydantic import BaseModel
from pydantic_yaml import YamlModel

from feedly_regexp_marker.lib.feedly_controller import (
    Entry,
    action_t,
    stream_id_t,
)

T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")

pattern_text_t = str
entry_attr_t = Literal["title", "content"]


class EntryPatternTexts(BaseModel):
    class Config:
        frozen = True

    title: frozenset[pattern_text_t] = frozenset()
    content: frozenset[pattern_text_t] = frozenset()


class Rule(BaseModel):
    class Config:
        frozen = True

    stream_ids: frozenset[stream_id_t]
    actions: frozenset[action_t]
    patterns: EntryPatternTexts
    name: Optional[str] = None

    def to_rules_dict(self) -> RulesDict:
        return RulesDict(
            __root__={
                action: {
                    stream_id: {
                        cast(entry_attr_t, entry_attr): pattern_text_set
                        for entry_attr, pattern_text_set in self.patterns
                    }
                    for stream_id in self.stream_ids
                }
                for action in self.actions
            }
        )


class Rules(YamlModel):
    class Config:
        frozen = True

    __root__: frozenset[Rule]

    def __iter__(self):
        yield from self.__root__

    def to_rules_dict(self) -> RulesDict:
        return merge_rules_dict(*[rule.to_rules_dict() for rule in self])


@overload
def merge_rules_dict(*args: frozenset[T]) -> frozenset[T]:
    ...


@overload
def merge_rules_dict(
    *args: dict[T1, frozenset[T2]]
) -> dict[T1, frozenset[T2]]:
    ...


@overload
def merge_rules_dict(*args: dict[T1, dict[T2, T3]]) -> dict[T1, dict[T2, T3]]:
    ...


@overload
def merge_rules_dict(*args: RulesDict) -> RulesDict:
    ...


def merge_rules_dict(*args):
    if all(isinstance(c, frozenset) for c in args):
        return frozenset({v for c in args for v in c})
    elif all(isinstance(x, dict) for x in args):
        return {
            k: merge_rules_dict(*[c[k] for c in args if k in c])
            for c in args
            for k in c.keys()
        }
    elif all(isinstance(x, RulesDict) for x in args):
        return RulesDict(
            __root__=merge_rules_dict(*[c.__root__ for c in args])
        )
    else:
        raise TypeError


class RulesDict(BaseModel):
    __root__: dict[
        action_t,
        dict[stream_id_t, dict[entry_attr_t, frozenset[pattern_text_t]]],
    ]

    def compile(self) -> compiled_rules_dict_t:
        @overload
        def __rec(data: frozenset[pattern_text_t]) -> Pattern[pattern_text_t]:
            ...

        @overload
        def __rec(
            data: dict[T1, frozenset[pattern_text_t]]
        ) -> dict[T1, Pattern[pattern_text_t]]:
            ...

        @overload
        def __rec(data: dict[T1, dict]) -> dict[T1, dict]:
            ...

        def __rec(data):
            if isinstance(data, frozenset):
                return re.compile("|".join(data)) if data else None
            elif isinstance(data, dict):
                return {k: __rec(v) for k, v in data.items()}
            else:
                raise

        return __rec(self.__root__)


compiled_rules_dict_t = dict[
    action_t,
    dict[stream_id_t, dict[entry_attr_t, Optional[Pattern[pattern_text_t]]]],
]


class Classifier:
    def __init__(
        self,
        compiled_rules_dict: compiled_rules_dict_t,
    ) -> None:
        self.__compiled_rules_dict = compiled_rules_dict

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> Classifier:
        return cls(Rules.parse_file(yaml_path).to_rules_dict().compile())

    def __to_act(self, entry: Entry, action: action_t) -> bool:
        if action not in self.__compiled_rules_dict:
            return False

        if (
            not entry.origin
            or entry.origin.stream_id not in self.__compiled_rules_dict[action]
        ):
            return False

        title_pattern = self.__compiled_rules_dict[action][
            entry.origin.stream_id
        ]["title"]
        if entry.title and title_pattern and title_pattern.search(entry.title):
            return True

        content_pattern = self.__compiled_rules_dict[action][
            entry.origin.stream_id
        ]["content"]
        if (
            entry.content
            and content_pattern
            and content_pattern.search(entry.content.content)
        ):
            return True

        return False

    def to_save(self, entry: Entry) -> bool:
        return self.__to_act(entry=entry, action="markAsSaved")

    def to_read(self, entry: Entry) -> bool:
        return self.__to_act(entry=entry, action="markAsRead")

from __future__ import annotations

import itertools
import re
from pathlib import Path
from re import Pattern
from typing import Literal, Optional, TypeVar, cast, overload

from pydantic import BaseModel
from pydantic_yaml import YamlModel

from feedly_regexp_marker.lib.feedly_controller import Action, Entry, StreamId

T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")

PatternText = str
EntryAttr = Literal["title", "content"]
CompiledRulesDict = dict[
    Action,
    dict[StreamId, dict[EntryAttr, Optional[Pattern[PatternText]]]],
]


class EntryPatternTexts(BaseModel):
    class Config:
        frozen = True

    title: frozenset[PatternText] = frozenset()
    content: frozenset[PatternText] = frozenset()


class Rule(BaseModel):
    class Config:
        frozen = True

    stream_ids: frozenset[StreamId]
    actions: frozenset[Action]
    patterns: EntryPatternTexts
    name: Optional[str] = None

    def to_rules_dict(self) -> RulesDict:
        return RulesDict(
            __root__={
                action: {
                    stream_id: {
                        cast(EntryAttr, entry_attr): pattern_text_set
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
def merge_rules_dict(*args: dict[T1, frozenset[T2]]) -> dict[T1, frozenset[T2]]:
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
        return RulesDict(__root__=merge_rules_dict(*[c.__root__ for c in args]))
    else:
        raise TypeError


class RulesDict(BaseModel):
    __root__: dict[
        Action,
        dict[StreamId, dict[EntryAttr, frozenset[PatternText]]],
    ]

    def compile(self) -> CompiledRulesDict:
        @overload
        def __rec(data: frozenset[PatternText]) -> Pattern[PatternText]:
            ...

        @overload
        def __rec(
            data: dict[T1, frozenset[PatternText]]
        ) -> dict[T1, Pattern[PatternText]]:
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


class Classifier:
    def __init__(
        self,
        compiled_rules_dict: CompiledRulesDict,
    ) -> None:
        self.__compiled_rules_dict = compiled_rules_dict

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> Classifier:
        if yaml_path.is_dir():
            return cls(
                merge_rules_dict(
                    *[
                        Rules.parse_file(p).to_rules_dict()
                        for p in itertools.chain(
                            yaml_path.glob("*.yaml"), yaml_path.glob("*.yml")
                        )
                    ]
                ).compile()
            )
        else:
            return cls(Rules.parse_file(yaml_path).to_rules_dict().compile())

    def __to_act(self, entry: Entry, action: Action) -> bool:
        if action not in self.__compiled_rules_dict:
            return False

        if (
            not entry.origin
            or entry.origin.stream_id not in self.__compiled_rules_dict[action]
        ):
            return False

        title_pattern = self.__compiled_rules_dict[action][entry.origin.stream_id][
            "title"
        ]
        if entry.title and title_pattern and title_pattern.search(entry.title):
            return True

        content_pattern = self.__compiled_rules_dict[action][entry.origin.stream_id][
            "content"
        ]
        if (
            entry.content
            and content_pattern
            and content_pattern.search(entry.content.content)
        ) or (
            entry.summary
            and content_pattern
            and content_pattern.search(entry.summary.content)
        ):
            return True

        return False

    def to_save(self, entry: Entry) -> bool:
        return self.__to_act(entry=entry, action="markAsSaved")

    def to_read(self, entry: Entry) -> bool:
        return self.__to_act(entry=entry, action="markAsRead")

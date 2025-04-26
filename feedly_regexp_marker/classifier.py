from __future__ import annotations

import itertools
import re
from pathlib import Path
from re import Pattern
from typing import Literal, Optional, TypeVar, cast, overload

from pydantic import RootModel

from feedly_regexp_marker.feedly_controller import Action, Entry, StreamId
from feedly_regexp_marker.rules import PatternText, Rule, Rules

T = TypeVar("T")
T1 = TypeVar("T1")
T2 = TypeVar("T2")
T3 = TypeVar("T3")

EntryAttr = Literal["title", "content"]
CompiledRulesDict = dict[
    Action,
    dict[StreamId, dict[EntryAttr, Optional[Pattern[PatternText]]]],
]


def rule_to_rules_dict(rule: Rule) -> RulesDict:
    return RulesDict(
        root={
            action: {
                stream_id: {
                    cast(EntryAttr, entry_attr): pattern_text_set
                    for entry_attr, pattern_text_set in rule.patterns
                }
                for stream_id in rule.stream_ids
            }
            for action in rule.actions
        }
    )


def rules_to_rules_dict(rules: Rules) -> RulesDict:
    return merge_rules_dict(*[rule_to_rules_dict(rule) for rule in rules])


@overload
def merge_rules_dict(*args: frozenset[T]) -> frozenset[T]: ...


@overload
def merge_rules_dict(*args: dict[T1, frozenset[T2]]) -> dict[T1, frozenset[T2]]: ...


@overload
def merge_rules_dict(*args: dict[T1, dict[T2, T3]]) -> dict[T1, dict[T2, T3]]: ...


@overload
def merge_rules_dict(*args: RulesDict) -> RulesDict: ...


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
        return RulesDict(root=merge_rules_dict(*[c.root for c in args]))
    else:
        raise TypeError


class RulesDict(
    RootModel[
        dict[
            Action,
            dict[StreamId, dict[EntryAttr, frozenset[PatternText]]],
        ]
    ]
):
    def compile(self) -> CompiledRulesDict:
        @overload
        def __rec(data: frozenset[PatternText]) -> Pattern[PatternText]: ...

        @overload
        def __rec(
            data: dict[T1, frozenset[PatternText]],
        ) -> dict[T1, Pattern[PatternText]]: ...

        @overload
        def __rec(data: dict[T1, dict]) -> dict[T1, dict]: ...

        def __rec(data):
            if isinstance(data, frozenset):
                return re.compile("|".join(data)) if data else None
            elif isinstance(data, dict):
                return {k: __rec(v) for k, v in data.items()}
            else:
                raise

        return __rec(self.root)


class Classifier:
    def __init__(
        self,
        compiled_rules_dict: CompiledRulesDict,
    ) -> None:
        self.__compiled_rules_dict = compiled_rules_dict

    @classmethod
    def from_yml(cls, yml_path: Path) -> Classifier:
        if yml_path.is_dir():
            return cls(
                merge_rules_dict(
                    *[
                        rules_to_rules_dict(Rules.from_yaml(p))
                        for p in itertools.chain(
                            yml_path.glob("*.yaml"), yml_path.glob("*.yml")
                        )
                    ]
                ).compile()
            )
        else:
            return cls(rules_to_rules_dict(Rules.from_yaml(yml_path)).compile())

    def __to_act(self, entry: Entry, action: Action) -> bool:
        if action not in self.__compiled_rules_dict:
            return False

        if (
            not entry.origin
            or entry.origin.streamId not in self.__compiled_rules_dict[action]
        ):
            return False

        title_pattern = self.__compiled_rules_dict[action][entry.origin.streamId][
            "title"
        ]
        if entry.title and title_pattern and title_pattern.search(entry.title):
            return True

        content_pattern = self.__compiled_rules_dict[action][entry.origin.streamId][
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

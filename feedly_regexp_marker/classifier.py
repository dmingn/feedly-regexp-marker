from __future__ import annotations

import functools
import itertools
import operator
from collections import defaultdict
from pathlib import Path
from re import Pattern
from typing import Literal, Mapping, Optional, cast

from pydantic import BaseModel, ConfigDict, RootModel

from feedly_regexp_marker.feedly_controller import Action, Entry, StreamId
from feedly_regexp_marker.pattern_texts import PatternTexts
from feedly_regexp_marker.rules import Rule, Rules

EntryAttr = Literal["title", "content"]


class RulePatternIndex(
    RootModel[dict[tuple[Action, StreamId, EntryAttr], PatternTexts]]
):
    model_config = ConfigDict(frozen=True)

    def __init__(
        self,
        root: Optional[
            Mapping[tuple[Action, StreamId, EntryAttr], PatternTexts]
        ] = None,
    ) -> None:
        super().__init__(root=dict(root or {}))

    def __or__(self, other: RulePatternIndex) -> RulePatternIndex:
        merged_root: defaultdict[tuple[Action, StreamId, EntryAttr], PatternTexts] = (
            defaultdict(lambda: PatternTexts(frozenset()))
        )

        for root in [self.root, other.root]:
            for key, pattern_text_set in root.items():
                merged_root[key] |= pattern_text_set

        return RulePatternIndex.model_validate(merged_root)

    @classmethod
    def from_rule(cls, rule: Rule) -> RulePatternIndex:
        return cls(
            root={
                (action, stream_id, cast(EntryAttr, entry_attr)): pattern_text_set
                for action in rule.actions
                for stream_id in rule.stream_ids
                for entry_attr, pattern_text_set in rule.patterns.model_dump().items()
            }
        )

    @classmethod
    def from_rules(cls, rules: Rules) -> RulePatternIndex:
        return functools.reduce(
            operator.__or__,
            (cls.from_rule(rule) for rule in rules),
            cls(root={}),
        )


class Classifier(BaseModel):
    model_config = ConfigDict(frozen=True)

    compiled_rule_index: dict[tuple[Action, StreamId, EntryAttr], Optional[Pattern]]

    @classmethod
    def from_rule_pattern_index(
        cls, rule_pattern_index: RulePatternIndex
    ) -> Classifier:
        return cls(
            compiled_rule_index={
                key: pattern_texts.compile()
                for key, pattern_texts in rule_pattern_index.root.items()
            }
        )

    @classmethod
    def from_yml(cls, yml_path: Path) -> Classifier:
        yaml_file_paths = (
            itertools.chain(yml_path.glob("*.yaml"), yml_path.glob("*.yml"))
            if yml_path.is_dir()
            else [yml_path]
        )

        return cls.from_rule_pattern_index(
            functools.reduce(
                operator.__or__,
                (
                    RulePatternIndex.from_rules(Rules.from_yaml(p))
                    for p in yaml_file_paths
                ),
                RulePatternIndex(),
            )
        )

    def __to_act(self, entry: Entry, action: Action) -> bool:
        if not entry.origin:
            return False

        title_pattern = self.compiled_rule_index.get(
            (action, entry.origin.streamId, "title")
        )
        if entry.title and title_pattern and title_pattern.search(entry.title):
            return True

        content_pattern = self.compiled_rule_index.get(
            (action, entry.origin.streamId, "content")
        )
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

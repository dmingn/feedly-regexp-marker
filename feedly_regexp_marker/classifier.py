from __future__ import annotations

import functools
import itertools
import operator
import re
from collections import defaultdict
from pathlib import Path
from re import Pattern
from typing import Literal, Optional, cast

from pydantic import ConfigDict, RootModel

from feedly_regexp_marker.feedly_controller import Action, Entry, StreamId
from feedly_regexp_marker.rules import PatternText, Rule, Rules

EntryAttr = Literal["title", "content"]


class PatternTexts(RootModel[frozenset[PatternText]]):
    model_config = ConfigDict(frozen=True)

    def __or__(self, other: PatternTexts) -> PatternTexts:
        return PatternTexts.model_validate(self.root | other.root)

    def compile(self) -> Optional[Pattern[PatternText]]:
        if not self.root:
            return None
        return re.compile("|".join(self.root))


class RulePatternIndex(
    RootModel[dict[tuple[Action, StreamId, EntryAttr], PatternTexts]]
):
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
                for entry_attr, pattern_text_set in rule.patterns
            }
        )

    @classmethod
    def from_rules(cls, rules: Rules) -> RulePatternIndex:
        return functools.reduce(operator.__or__, rules)


class Classifier(
    RootModel[dict[tuple[Action, StreamId, EntryAttr], Optional[Pattern[PatternText]]]]
):
    @classmethod
    def from_rule_pattern_index(
        cls, rule_pattern_index: RulePatternIndex
    ) -> Classifier:
        return cls.model_validate(
            {
                key: pattern_texts.compile() if pattern_texts else None
                for key, pattern_texts in rule_pattern_index.root.items()
            }
        )

    @classmethod
    def from_yml(cls, yml_path: Path) -> Classifier:
        if yml_path.is_dir():
            return cls.from_rule_pattern_index(
                functools.reduce(
                    operator.__or__,
                    [
                        RulePatternIndex.from_rules(Rules.from_yaml(p))
                        for p in itertools.chain(
                            yml_path.glob("*.yaml"), yml_path.glob("*.yml")
                        )
                    ],
                )
            )
        else:
            return cls.from_rule_pattern_index(
                RulePatternIndex.from_rules(Rules.from_yaml(yml_path))
            )

    def __to_act(self, entry: Entry, action: Action) -> bool:
        if action not in self.root:
            return False

        if not entry.origin:
            return False

        try:
            title_pattern = self.root[(action, entry.origin.streamId, "title")]
        except KeyError:
            pass
        else:
            if entry.title and title_pattern and title_pattern.search(entry.title):
                return True

        try:
            content_pattern = self.root[(action, entry.origin.streamId, "content")]
        except KeyError:
            pass
        else:
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

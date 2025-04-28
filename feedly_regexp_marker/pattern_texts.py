from __future__ import annotations

import re
from re import Pattern
from typing import Annotated, Optional

from pydantic import ConfigDict, RootModel, StringConstraints

PatternText = Annotated[str, StringConstraints(min_length=1)]


class PatternTexts(RootModel[frozenset[PatternText]]):
    model_config = ConfigDict(frozen=True)

    def __init__(self, root: frozenset[PatternText] = frozenset()) -> None:
        super().__init__(root=root)

    def __or__(self, other: PatternTexts) -> PatternTexts:
        return PatternTexts.model_validate(self.root | other.root)

    def compile(self) -> Optional[Pattern]:
        if not self.root:
            return None
        return re.compile("|".join(self.root))

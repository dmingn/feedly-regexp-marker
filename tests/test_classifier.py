import pytest
from pydantic import ValidationError

from feedly_regexp_marker.classifier import RulePatternIndex
from feedly_regexp_marker.pattern_texts import PatternTexts

# === Test RulePatternIndex ===


class TestRulePatternIndex:

    # --- Test Initialization and Immutability ---
    @pytest.mark.parametrize(
        "init_kwargs, expected_root",
        [
            pytest.param({}, {}, id="no_args"),
            pytest.param({"root": None}, {}, id="root_none"),
            pytest.param({"root": {}}, {}, id="root_empty_dict"),
            pytest.param(
                {"root": {("markAsRead", "s1", "title"): PatternTexts(["title"])}},
                {("markAsRead", "s1", "title"): PatternTexts(["title"])},
                id="with_data",
            ),
        ],
    )
    def test_initialization(self, init_kwargs: dict, expected_root: dict):
        """Tests RulePatternIndex initialization for various scenarios."""
        rpi = RulePatternIndex(**init_kwargs)
        assert rpi.root == expected_root
        assert rpi.model_config.get("frozen") is True

    def test_frozen(self):
        """Test RulePatternIndex is immutable due to frozen=True."""
        rpi = RulePatternIndex(
            root={("markAsRead", "s1", "title"): PatternTexts(["title"])}
        )
        with pytest.raises(ValidationError):
            # Pydantic v2 raises ValidationError on mutation attempts for frozen models
            rpi.root = {}  # type: ignore[misc]

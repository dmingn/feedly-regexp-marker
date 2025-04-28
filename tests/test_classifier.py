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

    # --- Test __or__ operator ---
    @pytest.mark.parametrize(
        "rpi1_data, rpi2_data, expected_root_data",
        [
            pytest.param({}, {}, {}, id="empty_or_empty"),
            pytest.param(
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },
                {},
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },
                id="nonempty_or_empty",
            ),
            pytest.param(
                {},
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },
                id="empty_or_nonempty",
            ),
            pytest.param(
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },
                {
                    ("markAsSaved", "s1", "title"): PatternTexts(["title_B"]),
                    ("markAsSaved", "s1", "content"): PatternTexts(),
                },
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                    ("markAsSaved", "s1", "title"): PatternTexts(["title_B"]),
                    ("markAsSaved", "s1", "content"): PatternTexts(),
                },
                id="disjoint_keys",
            ),
            pytest.param(
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_B"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },  # Overlaps key
                {
                    ("markAsRead", "s1", "title"): PatternTexts(
                        ["title_A", "title_B"]
                    ),  # Merged PatternTexts
                    (
                        "markAsRead",
                        "s1",
                        "content",
                    ): PatternTexts(),  # Merged empty PatternTexts
                },
                id="overlapping_keys",
            ),
            pytest.param(
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(["content_X"]),
                },
                {
                    ("markAsSaved", "s1", "title"): PatternTexts(["title_B"]),
                    ("markAsSaved", "s1", "content"): PatternTexts(),
                },
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(["content_X"]),
                    ("markAsSaved", "s1", "title"): PatternTexts(["title_B"]),
                    ("markAsSaved", "s1", "content"): PatternTexts(),
                },
                id="mixed_overlap",
            ),
            pytest.param(  # Idempotency check
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(["content_X"]),
                },
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(["content_X"]),
                },
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["title_A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(["content_X"]),
                },
                id="idempotency",
            ),
        ],
    )
    def test_or_operator(
        self, rpi1_data: dict, rpi2_data: dict, expected_root_data: dict
    ):
        """Tests the __or__ operator for RulePatternIndex using parametrize."""
        rpi1 = RulePatternIndex(root=rpi1_data)
        rpi2 = RulePatternIndex(root=rpi2_data)
        expected_rpi = RulePatternIndex(root=expected_root_data)

        # --- Test the | operator ---
        result = rpi1 | rpi2
        assert isinstance(result, RulePatternIndex)
        assert result.root == expected_rpi.root
        assert result.model_config.get("frozen") is True  # Ensure result is also frozen

        # --- Test immutability of original instances ---
        assert rpi1.root == rpi1_data
        assert rpi2.root == rpi2_data

        # --- Test commutativity (a | b == b | a) ---
        result_reversed = rpi2 | rpi1
        assert result_reversed.root == expected_rpi.root

import pytest
from pydantic import ValidationError

from feedly_regexp_marker.classifier import EntryAttr, RulePatternIndex
from feedly_regexp_marker.feedly_controller import Action, StreamId
from feedly_regexp_marker.pattern_texts import PatternTexts
from feedly_regexp_marker.rules import EntryPatternTexts, Rule

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

    # --- Test from_rule ---
    def test_from_rule_basic_title_only(self):
        """Test from_rule with 1 action, 1 stream, title pattern only."""
        rule = Rule(
            stream_ids=frozenset(["s1"]),
            actions=frozenset(["markAsRead"]),
            patterns=EntryPatternTexts(title=PatternTexts(["A"])),
        )
        rpi = RulePatternIndex.from_rule(rule)

        expected_key_t = ("markAsRead", "s1", "title")
        expected_key_c = ("markAsRead", "s1", "content")
        expected_root = {
            expected_key_t: PatternTexts(["A"]),
            expected_key_c: PatternTexts(),  # model_dump() includes empty content
        }
        assert rpi.root == expected_root

    def test_from_rule_basic_content_only(self):
        """Test from_rule with 1 action, 1 stream, content pattern only."""
        rule = Rule(
            stream_ids=frozenset(["s1"]),
            actions=frozenset(["markAsRead"]),
            patterns=EntryPatternTexts(content=PatternTexts(["X"])),
        )
        rpi = RulePatternIndex.from_rule(rule)

        expected_key_t = ("markAsRead", "s1", "title")
        expected_key_c = ("markAsRead", "s1", "content")
        expected_root = {
            expected_key_t: PatternTexts(),  # model_dump() includes empty title
            expected_key_c: PatternTexts(["X"]),
        }
        assert rpi.root == expected_root

    def test_from_rule_both_attrs(self):
        """Test from_rule with 1 action, 1 stream, both title and content patterns."""
        rule = Rule(
            stream_ids=frozenset(["s1"]),
            actions=frozenset(["markAsRead"]),
            patterns=EntryPatternTexts(
                title=PatternTexts(["A"]), content=PatternTexts(["X"])
            ),
        )
        rpi = RulePatternIndex.from_rule(rule)

        expected_key_t = ("markAsRead", "s1", "title")
        expected_key_c = ("markAsRead", "s1", "content")
        expected_root = {
            expected_key_t: PatternTexts(["A"]),
            expected_key_c: PatternTexts(["X"]),
        }
        assert rpi.root == expected_root

    def test_from_rule_multiple_actions(self):
        """Test from_rule with multiple actions."""
        rule = Rule(
            stream_ids=frozenset(["s1"]),
            actions=frozenset(["markAsRead", "markAsSaved"]),  # Multiple actions
            patterns=EntryPatternTexts(title=PatternTexts(["A"])),
        )
        rpi = RulePatternIndex.from_rule(rule)

        expected_key_read_t = ("markAsRead", "s1", "title")
        expected_key_read_c = ("markAsRead", "s1", "content")
        expected_key_save_t = ("markAsSaved", "s1", "title")
        expected_key_save_c = ("markAsSaved", "s1", "content")
        expected_root = {
            expected_key_read_t: PatternTexts(["A"]),
            expected_key_read_c: PatternTexts(),
            expected_key_save_t: PatternTexts(["A"]),
            expected_key_save_c: PatternTexts(),
        }
        assert rpi.root == expected_root

    def test_from_rule_multiple_streams(self):
        """Test from_rule with multiple stream IDs."""
        rule = Rule(
            stream_ids=frozenset(["s1", "s2"]),  # Multiple streams
            actions=frozenset(["markAsRead"]),
            patterns=EntryPatternTexts(title=PatternTexts(["A"])),
        )
        rpi = RulePatternIndex.from_rule(rule)

        expected_key_s1_t = ("markAsRead", "s1", "title")
        expected_key_s1_c = ("markAsRead", "s1", "content")
        expected_key_s2_t = ("markAsRead", "s2", "title")
        expected_key_s2_c = ("markAsRead", "s2", "content")
        expected_root = {
            expected_key_s1_t: PatternTexts(["A"]),
            expected_key_s1_c: PatternTexts(),
            expected_key_s2_t: PatternTexts(["A"]),
            expected_key_s2_c: PatternTexts(),
        }
        assert rpi.root == expected_root

    def test_from_rule_multiple_actions_and_streams(self):
        """Test from_rule with multiple actions and stream IDs."""
        rule = Rule(
            stream_ids=frozenset(["s1", "s2"]),
            actions=frozenset(["markAsRead", "markAsSaved"]),
            patterns=EntryPatternTexts(title=PatternTexts(["A"])),
        )
        rpi = RulePatternIndex.from_rule(rule)

        expected_keys: list[tuple[Action, StreamId, EntryAttr]] = [
            ("markAsRead", "s1", "title"),
            ("markAsRead", "s2", "title"),
            ("markAsSaved", "s1", "title"),
            ("markAsSaved", "s2", "title"),
            ("markAsRead", "s1", "content"),
            ("markAsRead", "s2", "content"),
            ("markAsSaved", "s1", "content"),
            ("markAsSaved", "s2", "content"),
        ]
        assert len(rpi.root) == len(expected_keys)
        for key in expected_keys:
            assert key in rpi.root
            if key[2] == "title":
                assert rpi.root[key] == PatternTexts(["A"])
            else:
                assert rpi.root[key] == PatternTexts()  # Empty content

    def test_from_rule_no_patterns(self):
        """Test from_rule with empty patterns results in keys with empty PatternTexts."""
        rule = Rule(
            stream_ids=frozenset(["s1"]),
            actions=frozenset(["markAsRead"]),
            patterns=EntryPatternTexts(),  # Empty patterns
        )
        rpi = RulePatternIndex.from_rule(rule)

        expected_key_t = ("markAsRead", "s1", "title")
        expected_key_c = ("markAsRead", "s1", "content")
        expected_root = {
            expected_key_t: PatternTexts(),
            expected_key_c: PatternTexts(),
        }
        assert rpi.root == expected_root

    def test_from_rule_empty_actions_or_streams(self):
        """Test from_rule with empty actions or stream_ids results in an empty index."""
        # Empty actions
        rule_empty_actions = Rule(
            stream_ids=frozenset(["s1"]),
            actions=frozenset(),  # Empty
            patterns=EntryPatternTexts(title=PatternTexts(["A"])),
        )
        rpi_empty_actions = RulePatternIndex.from_rule(rule_empty_actions)
        assert rpi_empty_actions.root == {}

        # Empty streams
        rule_empty_streams = Rule(
            stream_ids=frozenset(),  # Empty
            actions=frozenset(["markAsRead"]),
            patterns=EntryPatternTexts(title=PatternTexts(["A"])),
        )
        rpi_empty_streams = RulePatternIndex.from_rule(rule_empty_streams)
        assert rpi_empty_streams.root == {}

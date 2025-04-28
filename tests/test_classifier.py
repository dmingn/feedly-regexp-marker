import pytest
from pydantic import ValidationError

from feedly_regexp_marker.classifier import EntryAttr, RulePatternIndex
from feedly_regexp_marker.feedly_controller import Action, StreamId
from feedly_regexp_marker.pattern_texts import PatternTexts
from feedly_regexp_marker.rules import EntryPatternTexts, Rule, Rules

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
    @pytest.mark.parametrize(
        "input_rule, expected_root_data",
        [
            # Basic title only
            pytest.param(
                Rule(
                    stream_ids=frozenset(["s1"]),
                    actions=frozenset(["markAsRead"]),
                    patterns=EntryPatternTexts(title=PatternTexts(["A"])),
                ),
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },
                id="basic_title_only",
            ),
            # Basic content only
            pytest.param(
                Rule(
                    stream_ids=frozenset(["s1"]),
                    actions=frozenset(["markAsRead"]),
                    patterns=EntryPatternTexts(content=PatternTexts(["X"])),
                ),
                {
                    ("markAsRead", "s1", "title"): PatternTexts(),
                    ("markAsRead", "s1", "content"): PatternTexts(["X"]),
                },
                id="basic_content_only",
            ),
            # Both attributes
            pytest.param(
                Rule(
                    stream_ids=frozenset(["s1"]),
                    actions=frozenset(["markAsRead"]),
                    patterns=EntryPatternTexts(
                        title=PatternTexts(["A"]), content=PatternTexts(["X"])
                    ),
                ),
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(["X"]),
                },
                id="both_attrs",
            ),
            # Multiple actions
            pytest.param(
                Rule(
                    stream_ids=frozenset(["s1"]),
                    actions=frozenset(["markAsRead", "markAsSaved"]),
                    patterns=EntryPatternTexts(title=PatternTexts(["A"])),
                ),
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                    ("markAsSaved", "s1", "title"): PatternTexts(["A"]),
                    ("markAsSaved", "s1", "content"): PatternTexts(),
                },
                id="multiple_actions",
            ),
            # Multiple streams
            pytest.param(
                Rule(
                    stream_ids=frozenset(["s1", "s2"]),
                    actions=frozenset(["markAsRead"]),
                    patterns=EntryPatternTexts(title=PatternTexts(["A"])),
                ),
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                    ("markAsRead", "s2", "title"): PatternTexts(["A"]),
                    ("markAsRead", "s2", "content"): PatternTexts(),
                },
                id="multiple_streams",
            ),
            # Multiple actions and streams
            pytest.param(
                Rule(
                    stream_ids=frozenset(["s1", "s2"]),
                    actions=frozenset(["markAsRead", "markAsSaved"]),
                    patterns=EntryPatternTexts(title=PatternTexts(["A"])),
                ),
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                    ("markAsRead", "s2", "title"): PatternTexts(["A"]),
                    ("markAsRead", "s2", "content"): PatternTexts(),
                    ("markAsSaved", "s1", "title"): PatternTexts(["A"]),
                    ("markAsSaved", "s1", "content"): PatternTexts(),
                    ("markAsSaved", "s2", "title"): PatternTexts(["A"]),
                    ("markAsSaved", "s2", "content"): PatternTexts(),
                },
                id="multiple_actions_and_streams",
            ),
            # No patterns (empty EntryPatternTexts)
            pytest.param(
                Rule(
                    stream_ids=frozenset(["s1"]),
                    actions=frozenset(["markAsRead"]),
                    patterns=EntryPatternTexts(),
                ),
                {
                    ("markAsRead", "s1", "title"): PatternTexts(),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },
                id="no_patterns",
            ),
        ],
    )
    def test_from_rule_parametrized(self, input_rule: Rule, expected_root_data: dict):
        """Tests RulePatternIndex.from_rule for various valid rule inputs."""
        rpi = RulePatternIndex.from_rule(input_rule)
        assert rpi.root == expected_root_data

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

    # --- Test from_rules ---
    def test_from_rules_empty(self):
        """Test from_rules with an empty Rules set returns an empty index."""
        empty_rules = Rules(root=frozenset())
        rpi = RulePatternIndex.from_rules(empty_rules)
        assert rpi.root == {}

    @pytest.mark.parametrize(
        "input_rules_list, expected_root_data",
        [
            # Single rule
            pytest.param(
                [
                    Rule(  # Single Rule: Read S1 Title A
                        stream_ids=frozenset(["s1"]),
                        actions=frozenset(["markAsRead"]),
                        patterns=EntryPatternTexts(title=PatternTexts(["A"])),
                    )
                ],
                {
                    ("markAsRead", "s1", "title"): PatternTexts(["A"]),
                    ("markAsRead", "s1", "content"): PatternTexts(),
                },
                id="single_rule",
            ),
            # Mixed disjoint and overlapping
            pytest.param(
                [
                    Rule(  # Rule 1: Read S1 Title A
                        stream_ids=frozenset(["s1"]),
                        actions=frozenset(["markAsRead"]),
                        patterns=EntryPatternTexts(title=PatternTexts(["A"])),
                    ),
                    Rule(  # Rule 2: Read S1 Title B (overlaps with Rule 1)
                        stream_ids=frozenset(["s1"]),
                        actions=frozenset(["markAsRead"]),
                        patterns=EntryPatternTexts(title=PatternTexts(["B"])),
                    ),
                    Rule(  # Rule 3: Save S2 Content X (disjoint)
                        stream_ids=frozenset(["s2"]),
                        actions=frozenset(["markAsSaved"]),
                        patterns=EntryPatternTexts(content=PatternTexts(["X"])),
                    ),
                ],
                {
                    # from Rule 1 | Rule 2
                    ("markAsRead", "s1", "title"): PatternTexts(["A", "B"]),  # Merged
                    ("markAsRead", "s1", "content"): PatternTexts(),  # Merged empty
                    # from Rule 3
                    ("markAsSaved", "s2", "title"): PatternTexts(),
                    ("markAsSaved", "s2", "content"): PatternTexts(["X"]),
                },
                id="mixed_disjoint_and_overlapping",
            ),
        ],
    )
    def test_from_rules_parametrized(
        self, input_rules_list: list[Rule], expected_root_data: dict
    ):
        """Tests RulePatternIndex.from_rules with various numbers of rules."""
        input_rules = Rules(root=frozenset(input_rules_list))
        rpi = RulePatternIndex.from_rules(input_rules)
        assert rpi.root == expected_root_data

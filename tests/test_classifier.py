import re
from typing import Optional

import pytest
from pydantic import ValidationError

from feedly_regexp_marker.classifier import Classifier, EntryAttr, RulePatternIndex
from feedly_regexp_marker.feedly_controller import Action, Entry, StreamId
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


# === Test Classifier ===


class TestClassifier:

    # --- Test Initialization and Immutability ---
    def test_classifier_initialization_empty(self):
        """Test initializing Classifier with an empty compiled_rule_index."""
        classifier = Classifier(compiled_rule_index={})
        assert classifier.compiled_rule_index == {}
        assert classifier.model_config.get("frozen") is True

    def test_classifier_initialization_with_data(self):
        """Test initializing Classifier with valid compiled_rule_index data."""
        compiled_pattern_a = re.compile("A")
        compiled_pattern_b = re.compile("B")
        valid_data: dict[tuple[Action, StreamId, EntryAttr], Optional[re.Pattern]] = {
            ("markAsRead", "s1", "title"): compiled_pattern_a,
            ("markAsRead", "s1", "content"): None,
            ("markAsSaved", "s2", "title"): compiled_pattern_b,
        }
        classifier = Classifier(compiled_rule_index=valid_data)
        assert classifier.compiled_rule_index == valid_data
        # Check if patterns are correctly stored
        assert (
            classifier.compiled_rule_index[("markAsRead", "s1", "title")]
            is compiled_pattern_a
        )
        assert classifier.compiled_rule_index[("markAsRead", "s1", "content")] is None
        assert classifier.model_config.get("frozen") is True

    def test_classifier_frozen(self):
        """Test Classifier is immutable due to frozen=True."""
        classifier = Classifier(
            compiled_rule_index={("markAsRead", "s1", "title"): re.compile("A")}
        )
        # Test attribute reassignment
        with pytest.raises(ValidationError):
            classifier.compiled_rule_index = {}  # type: ignore[misc]

    # --- Test from_rule_pattern_index ---
    def test_from_rule_pattern_index_empty(self):
        """Test creating Classifier from an empty RulePatternIndex."""
        empty_rpi = RulePatternIndex()
        classifier = Classifier.from_rule_pattern_index(empty_rpi)
        assert classifier.compiled_rule_index == {}

    def test_from_rule_pattern_index_with_data(self):
        """Test creating Classifier from RulePatternIndex with data."""
        key1: tuple[Action, StreamId, EntryAttr] = ("markAsRead", "s1", "title")
        key2: tuple[Action, StreamId, EntryAttr] = ("markAsRead", "s1", "content")
        key3: tuple[Action, StreamId, EntryAttr] = ("markAsSaved", "s2", "title")

        pt1 = PatternTexts(["A", "B"])  # Non-empty
        pt2 = PatternTexts()  # Empty
        pt3 = PatternTexts(["C"])  # Non-empty

        rpi = RulePatternIndex(root={key1: pt1, key2: pt2, key3: pt3})
        classifier = Classifier.from_rule_pattern_index(rpi)

        # Check keys exist
        assert key1 in classifier.compiled_rule_index
        assert key2 in classifier.compiled_rule_index
        assert key3 in classifier.compiled_rule_index
        assert len(classifier.compiled_rule_index) == 3

        # Check compiled patterns (value types and content)
        compiled1 = classifier.compiled_rule_index[key1]
        compiled2 = classifier.compiled_rule_index[key2]
        compiled3 = classifier.compiled_rule_index[key3]

        assert isinstance(compiled1, re.Pattern)
        assert compiled2 is None  # Empty PatternTexts should compile to None
        assert isinstance(compiled3, re.Pattern)

    # --- Test to_act ---
    @pytest.fixture
    def classifier_for_to_act(self) -> Classifier:
        """Provides a Classifier instance for to_act tests."""
        # Define specific compiled rules for testing to_act logic
        compiled_rules: dict[
            tuple[Action, StreamId, EntryAttr], Optional[re.Pattern]
        ] = {
            # Read rules for stream 's1'
            ("markAsRead", "s1", "title"): re.compile(r"Important|Alert"),
            ("markAsRead", "s1", "content"): re.compile(r"keyword|secret"),
            # Save rules for stream 's1'
            ("markAsSaved", "s1", "title"): re.compile(r"SaveMe"),
            # No save rule for s1 content
            # Read rules for stream 's2'
            ("markAsRead", "s2", "title"): None,  # Explicitly None
            ("markAsRead", "s2", "content"): re.compile(r"projectX"),
        }
        return Classifier(compiled_rule_index=compiled_rules)

    # --- Test cases for to_act ---
    @pytest.mark.parametrize(
        "entry_data, action, expected_result",
        [
            # 1. No origin
            pytest.param(
                {"id": "e0", "title": "Test"}, "markAsRead", False, id="no_origin"
            ),
            # 2. No matching key in compiled_rule_index (stream 's3')
            pytest.param(
                {"id": "e1", "title": "Important", "origin": {"streamId": "s3"}},
                "markAsRead",
                False,
                id="no_matching_stream",
            ),
            # 3. No matching key in compiled_rule_index (save action for s1 content)
            pytest.param(
                {
                    "id": "e2",
                    "title": "News",
                    "content": {"content": "SaveMe"},
                    "origin": {"streamId": "s1"},
                },
                "markAsSaved",
                False,
                id="no_matching_content_key_for_save",  # Title rule exists, but content doesn't match title
            ),
            # 4. Title match (Read, s1)
            pytest.param(
                {
                    "id": "e3",
                    "title": "Alert: System Down",
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                True,
                id="title_match_read_s1_alert",
            ),
            pytest.param(
                {
                    "id": "e4",
                    "title": "This is Important",
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                True,
                id="title_match_read_s1_important",
            ),
            # 5. Title no match (Read, s1) -> check content/summary
            pytest.param(
                {"id": "e5", "title": "Regular News", "origin": {"streamId": "s1"}},
                "markAsRead",
                False,
                id="title_no_match_read_s1_no_content",
            ),
            # 6. Title match (Save, s1)
            pytest.param(
                {
                    "id": "e6",
                    "title": "Please SaveMe Now",
                    "origin": {"streamId": "s1"},
                },
                "markAsSaved",
                True,
                id="title_match_save_s1",
            ),
            # 7. Title no match (Save, s1)
            pytest.param(
                {"id": "e7", "title": "Do Not Save", "origin": {"streamId": "s1"}},
                "markAsSaved",
                False,
                id="title_no_match_save_s1",
            ),
            # 8. Content match (Read, s1) - Title doesn't match
            pytest.param(
                {
                    "id": "e8",
                    "title": "News",
                    "content": {"content": "Found keyword"},
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                True,
                id="content_match_read_s1_keyword",
            ),
            pytest.param(
                {
                    "id": "e9",
                    "title": "News",
                    "content": {"content": "The secret word"},
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                True,
                id="content_match_read_s1_secret",
            ),
            # 9. Content no match (Read, s1)
            pytest.param(
                {
                    "id": "e10",
                    "title": "News",
                    "content": {"content": "Nothing relevant"},
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                False,
                id="content_no_match_read_s1",
            ),
            # 10. Summary match (Read, s1) - Title/Content don't match
            pytest.param(
                {
                    "id": "e11",
                    "title": "News",
                    "summary": {"content": "Summary has keyword"},
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                True,
                id="summary_match_read_s1_keyword",
            ),
            pytest.param(
                {
                    "id": "e12",
                    "title": "News",
                    "content": {"content": "No match"},
                    "summary": {"content": "Summary has secret"},
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                True,
                id="summary_match_read_s1_secret_content_no_match",
            ),
            # 11. Summary no match (Read, s1)
            pytest.param(
                {
                    "id": "e13",
                    "title": "News",
                    "summary": {"content": "Nothing relevant"},
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                False,
                id="summary_no_match_read_s1",
            ),
            # 12. Title is None
            pytest.param(
                {
                    "id": "e14",
                    "title": None,
                    "content": {"content": "keyword"},
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                True,
                id="title_none_content_match",
            ),
            # 13. Content and Summary are None
            pytest.param(
                {
                    "id": "e15",
                    "title": "Important",
                    "content": None,
                    "summary": None,
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                True,
                id="content_summary_none_title_match",
            ),
            pytest.param(
                {
                    "id": "e16",
                    "title": "News",
                    "content": None,
                    "summary": None,
                    "origin": {"streamId": "s1"},
                },
                "markAsRead",
                False,
                id="content_summary_none_title_no_match",
            ),
            # 14. Pattern is None in index (Read, s2, title)
            pytest.param(
                {"id": "e17", "title": "Any Title", "origin": {"streamId": "s2"}},
                "markAsRead",
                False,
                id="title_pattern_is_none",  # Should proceed to content check
            ),
            # 15. Pattern is None in index, but content matches (Read, s2)
            pytest.param(
                {
                    "id": "e18",
                    "title": "Any Title",
                    "content": {"content": "About projectX"},
                    "origin": {"streamId": "s2"},
                },
                "markAsRead",
                True,
                id="title_pattern_none_content_match",
            ),
        ],
    )
    def test_to_act(
        self,
        classifier_for_to_act: Classifier,
        entry_data: dict,
        action: Action,
        expected_result: bool,
    ):
        """Tests the to_act method for various scenarios."""
        # Create Entry object from data dictionary
        entry = Entry(**entry_data)
        assert classifier_for_to_act.to_act(entry, action) == expected_result

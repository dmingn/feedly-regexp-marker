from pathlib import Path

import pytest
from pydantic import ValidationError
from ruamel.yaml.parser import ParserError

from feedly_regexp_marker.rules import (
    Action,
    EntryPatternTexts,
    PatternText,
    Rule,
    Rules,
    StreamId,
)

# --- Test EntryPatternTexts ---


def test_entry_pattern_texts_defaults():
    """Test EntryPatternTexts initializes with default empty frozensets."""
    patterns = EntryPatternTexts()
    assert patterns.title == frozenset()
    assert patterns.content == frozenset()
    assert patterns.model_config.get("frozen") is True


def test_entry_pattern_texts_with_data():
    """Test EntryPatternTexts initialization with data."""
    title_patterns: frozenset[PatternText] = frozenset(["^Important:", "Alert"])
    content_patterns: frozenset[PatternText] = frozenset(["keyword1", "keyword2"])
    patterns = EntryPatternTexts(title=title_patterns, content=content_patterns)
    assert patterns.title == title_patterns
    assert patterns.content == content_patterns


def test_entry_pattern_texts_empty_patterntext():
    """Test EntryPatternTexts initialization with empty PatternText."""
    with pytest.raises(ValidationError):
        EntryPatternTexts(title=frozenset([""]))
    with pytest.raises(ValidationError):
        EntryPatternTexts(content=frozenset([""]))


def test_entry_pattern_texts_frozen():
    """Test EntryPatternTexts is immutable."""
    patterns = EntryPatternTexts(title=frozenset(["test"]))
    with pytest.raises(ValidationError):
        # Pydantic v2 raises ValidationError on mutation attempts for frozen models
        patterns.title = frozenset(["new"])  # type: ignore[misc]
    with pytest.raises(ValidationError):
        patterns.content = frozenset(["new"])  # type: ignore[misc]


# --- Test Rule ---


def test_rule_minimal():
    """Test minimal Rule initialization."""
    stream_ids: frozenset[StreamId] = frozenset(["feed/http://example.com/rss"])
    actions: frozenset[Action] = frozenset(["markAsRead"])
    patterns = EntryPatternTexts()
    rule = Rule(stream_ids=stream_ids, actions=actions, patterns=patterns)

    assert rule.stream_ids == stream_ids
    assert rule.actions == actions
    assert rule.patterns == patterns
    assert rule.name is None
    assert rule.model_config.get("frozen") is True


def test_rule_with_data():
    """Test Rule initialization with more data."""
    stream_ids: frozenset[StreamId] = frozenset(["feed/1", "feed/2"])
    actions: frozenset[Action] = frozenset(["markAsRead", "markAsSaved"])
    patterns = EntryPatternTexts(
        title=frozenset(["Title Pattern"]), content=frozenset(["Content Pattern"])
    )
    name = "My Test Rule"
    rule = Rule(stream_ids=stream_ids, actions=actions, patterns=patterns, name=name)

    assert rule.stream_ids == stream_ids
    assert rule.actions == actions
    assert rule.patterns == patterns
    assert rule.name == name


def test_rule_frozen():
    """Test Rule is immutable."""
    rule = Rule(
        stream_ids=frozenset(["feed/1"]),
        actions=frozenset(["markAsRead"]),
        patterns=EntryPatternTexts(),
    )
    with pytest.raises(ValidationError):
        rule.name = "New Name"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        rule.stream_ids = frozenset(["feed/2"])  # type: ignore[misc]
    with pytest.raises(ValidationError):
        rule.actions = frozenset(["markAsSaved"])  # type: ignore[misc]
    with pytest.raises(ValidationError):
        rule.patterns = EntryPatternTexts(title=frozenset(["new"]))  # type: ignore[misc]


# --- Test Rules ---


# Fixtures from existing tests (assuming they are in the same file or imported)
@pytest.fixture
def sample_rule1() -> Rule:
    return Rule(
        stream_ids=frozenset(["feed/1"]),
        actions=frozenset(["markAsRead"]),
        patterns=EntryPatternTexts(title=frozenset(["Rule1 Title"])),
        name="Rule 1",
    )


@pytest.fixture
def sample_rule2() -> Rule:
    return Rule(
        stream_ids=frozenset(["feed/2", "feed/3"]),
        actions=frozenset(["markAsSaved"]),
        patterns=EntryPatternTexts(content=frozenset(["Rule2 Content"])),
        name="Rule 2",
    )


def test_rules_initialization(sample_rule1: Rule, sample_rule2: Rule):
    """Test Rules initialization with a set of Rule objects."""
    rule_set = frozenset([sample_rule1, sample_rule2])
    rules = Rules(root=rule_set)
    assert rules.root == rule_set
    assert rules.model_config.get("frozen") is True


def test_rules_iteration(sample_rule1: Rule, sample_rule2: Rule):
    """Test iterating over Rules yields the individual Rule objects."""
    rule_set = frozenset([sample_rule1, sample_rule2])
    rules = Rules(root=rule_set)
    iterated_rules = list(rules)  # Uses the __iter__ method
    assert len(iterated_rules) == 2
    assert sample_rule1 in iterated_rules
    assert sample_rule2 in iterated_rules


def test_rules_frozen(sample_rule1: Rule):
    """Test Rules is immutable."""
    rules = Rules(root=frozenset([sample_rule1]))
    with pytest.raises(ValidationError):
        rules.root = frozenset()  # type: ignore[misc]


# --- Test Rules.from_yaml ---


def test_rules_from_yaml(tmp_path: Path, sample_rule1: Rule, sample_rule2: Rule):
    """Test loading Rules from a valid YAML file."""
    yaml_content = """
- stream_ids:
  - feed/1
  actions:
  - markAsRead
  patterns:
    title:
    - Rule1 Title
  name: Rule 1
- stream_ids:
  - feed/2
  - feed/3
  actions:
  - markAsSaved
  patterns:
    content:
    - Rule2 Content
  name: Rule 2
"""
    yaml_file = tmp_path / "rules.yaml"
    yaml_file.write_text(yaml_content)

    loaded_rules = Rules.from_yaml(yaml_file)

    expected_rules = Rules(root=frozenset([sample_rule1, sample_rule2]))

    # Compare frozensets directly (order doesn't matter)
    assert loaded_rules.root == expected_rules.root


def test_rules_from_empty_yaml(tmp_path: Path):
    """Test loading Rules from an empty YAML file (valid YAML list)."""
    yaml_content = "[]"  # Represents an empty list/set of rules
    yaml_file = tmp_path / "empty_rules.yaml"
    yaml_file.write_text(yaml_content)

    loaded_rules = Rules.from_yaml(yaml_file)
    assert loaded_rules.root == frozenset()


def test_rules_from_invalid_yaml_structure(tmp_path: Path):
    """Test loading Rules from YAML with invalid structure for Pydantic."""
    # stream_ids should be a list/set of strings, not int
    yaml_content = """
- stream_ids: 123
  actions: ["markAsRead"]
  patterns: {}
"""
    yaml_file = tmp_path / "invalid_rules.yaml"
    yaml_file.write_text(yaml_content)

    # pydantic-yaml wraps parsing errors in ValidationError
    with pytest.raises(ValidationError):
        Rules.from_yaml(yaml_file)


def test_rules_from_malformed_yaml(tmp_path: Path):
    """Test loading Rules from malformed YAML raises an error (from yaml parser)."""
    # This YAML is structurally invalid (bad indentation)
    yaml_content = """
- stream_ids: [feed/1]
  actions: [markAsRead]
  patterns:
    title: [Test]
 name: Unindented Name # Malformed YAML
"""
    yaml_file = tmp_path / "malformed_rules.yaml"
    yaml_file.write_text(yaml_content)

    # Expecting an error during YAML parsing
    with pytest.raises(ParserError):
        Rules.from_yaml(yaml_file)


def test_rules_from_nonexistent_yaml():
    """Test loading Rules from a non-existent file raises FileNotFoundError."""
    non_existent_path = Path("non_existent_rules.yaml")
    assert not non_existent_path.exists()  # Ensure it doesn't exist
    with pytest.raises(FileNotFoundError):
        Rules.from_yaml(non_existent_path)

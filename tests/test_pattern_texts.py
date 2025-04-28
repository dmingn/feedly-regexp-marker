import re
from typing import Optional

import pytest
from pydantic import ValidationError

from feedly_regexp_marker.pattern_texts import PatternText, PatternTexts

# --- Test Cases for PatternTexts ---


def test_pattern_texts_defaults():
    """Test PatternTexts initializes with default empty frozenset."""
    patterns = PatternTexts()
    assert patterns.root == frozenset()
    assert patterns.model_config.get("frozen") is True


def test_pattern_texts_with_data():
    """Test PatternTexts initialization with data."""
    data: frozenset[PatternText] = frozenset(["^Important:", "Alert"])
    patterns = PatternTexts(root=data)
    assert patterns.root == data


def test_pattern_texts_empty_patterntext():
    """Test PatternTexts initialization with empty PatternText."""
    with pytest.raises(ValidationError):
        PatternTexts(root=frozenset([""]))


def test_pattern_texts_frozen():
    """Test PatternTexts is immutable."""
    patterns = PatternTexts(root=frozenset(["test"]))
    with pytest.raises(ValidationError):
        # Pydantic v2 raises ValidationError on mutation attempts for frozen models
        patterns.root = frozenset(["new"])  # type: ignore[misc]


# --- Test Cases for PatternTexts.__or__ ---


@pytest.mark.parametrize(
    "set1, set2, expected_set",
    [
        pytest.param(frozenset(), frozenset(), frozenset(), id="empty_or_empty"),
        pytest.param(
            frozenset(["a"]), frozenset(), frozenset(["a"]), id="nonempty_or_empty"
        ),
        pytest.param(
            frozenset(), frozenset(["a"]), frozenset(["a"]), id="empty_or_nonempty"
        ),
        pytest.param(
            frozenset(["a", "b"]),
            frozenset(["c"]),
            frozenset(["a", "b", "c"]),
            id="disjoint_sets",
        ),
        pytest.param(
            frozenset(["a", "b"]),
            frozenset(["b", "c"]),
            frozenset(["a", "b", "c"]),
            id="overlapping_sets",
        ),
        pytest.param(
            frozenset(["a"]), frozenset(["a"]), frozenset(["a"]), id="identical_sets"
        ),
    ],
)
def test_pattern_texts_or(
    set1: frozenset[PatternText],
    set2: frozenset[PatternText],
    expected_set: frozenset[PatternText],
):
    """Tests the __or__ operator for PatternTexts using parametrize."""
    pt1 = PatternTexts(root=set1)
    pt2 = PatternTexts(root=set2)

    # --- Test the | operator ---
    result = pt1 | pt2
    assert isinstance(result, PatternTexts)
    assert result.root == expected_set

    # --- Test immutability of original instances ---
    assert pt1.root == set1
    assert pt2.root == set2

    # --- Test commutativity (a | b == b | a) ---
    result_reversed = pt2 | pt1
    assert result_reversed.root == expected_set


# --- Test Cases for PatternTexts.compile ---


def test_pattern_texts_compile_empty():
    """Test compiling an empty PatternTexts instance."""
    pt_empty = PatternTexts(root=frozenset())
    compiled = pt_empty.compile()
    assert compiled is None


def test_pattern_texts_compile_single_pattern():
    """Test compiling a PatternTexts instance with a single pattern."""
    pattern = "^start"
    pt_single = PatternTexts(root=frozenset([pattern]))
    compiled = pt_single.compile()

    assert isinstance(compiled, re.Pattern)
    assert compiled.pattern == pattern
    assert compiled.search("start of line")
    assert not compiled.search("middle start")


def test_pattern_texts_compile_multiple_patterns():
    """Test compiling a PatternTexts instance with multiple patterns."""
    patterns = frozenset(["apple", "banana", r"\d+"])
    pt_multiple = PatternTexts(root=patterns)
    compiled = pt_multiple.compile()

    assert isinstance(compiled, re.Pattern)
    assert all(p in compiled.pattern for p in patterns)
    assert "|" in compiled.pattern

    # Test matching
    assert compiled.search("I like apple pie")
    assert compiled.search("banana bread is good")
    assert compiled.search("the number is 123")
    assert not compiled.search("only orange")
    assert not compiled.search("no digits here")


def test_pattern_texts_compile_special_chars():
    """Test compiling patterns with regex special characters."""
    patterns = frozenset([r"^\d+$", r"end\."])  # Start/end anchors, escaped dot
    pt_special = PatternTexts(root=patterns)
    compiled = pt_special.compile()

    assert isinstance(compiled, re.Pattern)
    assert all(p in compiled.pattern for p in patterns)

    assert compiled.search("12345")  # Matches ^\d+$
    assert not compiled.search("123a")
    assert compiled.search("this is the end.")  # Matches end\.
    assert not compiled.search("this is the end?")


def test_pattern_texts_compile_with_pipe_in_pattern():
    """Test compiling patterns where a pattern itself contains a pipe."""
    patterns = frozenset(["a|b", "c"])  # "a|b" is treated as one pattern unit here
    pt = PatternTexts(root=patterns)
    compiled: Optional[re.Pattern] = pt.compile()

    assert isinstance(compiled, re.Pattern)
    # The resulting pattern should be "a|b|c" or "c|a|b"
    # It should match 'a', 'b', or 'c'
    possible_patterns = ("a|b|c", "c|a|b")
    assert compiled.pattern in possible_patterns

    # Test matching
    assert compiled.search("a")  # Matches the 'a' part of "a|b"
    assert compiled.search("b")  # Matches the 'b' part of "a|b"
    assert compiled.search("c")  # Matches "c"
    assert not compiled.search("d")
    assert compiled.search("contains a here")
    assert compiled.search("contains b here")
    assert compiled.search("contains c here")

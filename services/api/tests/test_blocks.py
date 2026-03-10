"""Tests for the text block auto-conversion utility."""

import uuid
from unittest.mock import MagicMock

import pytest

from src.api.blocks import _split_text_block


def _make_member(name: str, member_id: str | None = None) -> MagicMock:
    m = MagicMock()
    m.id = uuid.UUID(member_id) if member_id else uuid.uuid4()
    m.display_name = name
    return m


@pytest.fixture
def zimomo():
    return _make_member("Zimomo", "11111111-1111-1111-1111-111111111111")


@pytest.fixture
def member_map(zimomo):
    return {"zimomo": zimomo}


@pytest.fixture
def skill_names():
    return {"create-table", "create-work-table"}


class TestSplitTextBlock:
    def test_mixed_mention_skill_link(self, member_map, skill_names, zimomo):
        text = "Hey @Zimomo can you /create-table from [this file](data/raw/sales.csv)"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [
            {"type": "text", "value": "Hey "},
            {"type": "mention", "member_id": str(zimomo.id), "display_name": "Zimomo"},
            {"type": "text", "value": " can you "},
            {"type": "skill", "name": "create-table"},
            {"type": "text", "value": " from "},
            {"type": "link", "url": "data/raw/sales.csv", "label": "this file"},
        ]
        assert mentions == [str(zimomo.id)]

    def test_unknown_mention_stays_as_text(self, member_map, skill_names):
        text = "Hey @Unknown person"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [{"type": "text", "value": "Hey @Unknown person"}]
        assert mentions == []

    def test_unknown_skill_stays_as_text(self, member_map, skill_names):
        text = "Try /nonexistent please"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [{"type": "text", "value": "Try /nonexistent please"}]
        assert mentions == []

    def test_plain_text_unchanged(self, member_map, skill_names):
        text = "Hello world"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [{"type": "text", "value": "Hello world"}]
        assert mentions == []

    def test_markdown_link_only(self, member_map, skill_names):
        text = "Check [docs](README.md)"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [
            {"type": "text", "value": "Check "},
            {"type": "link", "url": "README.md", "label": "docs"},
        ]
        assert mentions == []

    def test_skill_in_url_not_matched(self, member_map, skill_names):
        """A /skill-name embedded in a URL should not be converted."""
        text = "Visit http://example.com/create-table"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [{"type": "text", "value": "Visit http://example.com/create-table"}]
        assert mentions == []

    def test_multiple_mentions_mixed_known_unknown(self, member_map, skill_names, zimomo):
        text = "@Zimomo and @Unknown and @Zimomo again"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [
            {"type": "mention", "member_id": str(zimomo.id), "display_name": "Zimomo"},
            {"type": "text", "value": " and @Unknown and "},
            {"type": "mention", "member_id": str(zimomo.id), "display_name": "Zimomo"},
            {"type": "text", "value": " again"},
        ]
        assert len(mentions) == 2

    def test_mention_case_insensitive(self, member_map, skill_names, zimomo):
        text = "Hello @zimomo"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [
            {"type": "text", "value": "Hello "},
            {"type": "mention", "member_id": str(zimomo.id), "display_name": "Zimomo"},
        ]
        assert mentions == [str(zimomo.id)]

    def test_empty_string(self, member_map, skill_names):
        blocks, mentions = _split_text_block("", member_map, skill_names)

        assert blocks == []
        assert mentions == []

    def test_skill_at_start_of_text(self, member_map, skill_names):
        text = "/create-table from sales.csv"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [
            {"type": "skill", "name": "create-table"},
            {"type": "text", "value": " from sales.csv"},
        ]

    def test_link_with_http_url(self, member_map, skill_names):
        text = "See [Google](https://google.com) for more"
        blocks, mentions = _split_text_block(text, member_map, skill_names)

        assert blocks == [
            {"type": "text", "value": "See "},
            {"type": "link", "url": "https://google.com", "label": "Google"},
            {"type": "text", "value": " for more"},
        ]

    def test_no_members_no_skills(self):
        text = "Hey @someone /do-thing [link](url)"
        blocks, mentions = _split_text_block(text, {}, set())

        # Only the markdown link converts (always converts)
        assert blocks == [
            {"type": "text", "value": "Hey @someone /do-thing "},
            {"type": "link", "url": "url", "label": "link"},
        ]
        assert mentions == []

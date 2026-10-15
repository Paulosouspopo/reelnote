import json

import pytest
from pydantic import ValidationError

from reelnote_worker.card import ReelCard, card_json_schema

from .fakes import SAMPLE_CARD


def test_valid_recipe_card() -> None:
    card = ReelCard.model_validate(SAMPLE_CARD)
    assert card.kind == "recipe"
    assert card.details.ingredients[0].quantity == "100 g"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "details",
    [
        {"kind": "workout", "level": "beginner", "exercises": [{"name": "Squat", "sets": 3, "reps": "12"}]},
        {"kind": "place", "places": [{"name": "Chez Gladines", "city": "Paris", "price_range": "€"}]},
        {"kind": "media", "items": [{"title": "Dune", "media_type": "book", "creator": "Frank Herbert"}]},
        {"kind": "product", "products": [{"name": "AeroPress", "price": "40 €"}]},
        {"kind": "tip", "steps": ["Ouvrir Réglages", "Activer Toucher le dos"]},
        {
            "kind": "learning",
            "concepts": [{"term": "Intérêts composés", "explanation": "Des intérêts sur les intérêts."}],
        },
        {"kind": "other"},
    ],
)
def test_every_kind_validates(details: dict) -> None:
    card = ReelCard.model_validate({**SAMPLE_CARD, "details": details})
    assert card.kind == details["kind"]


def test_long_texts_are_truncated_not_rejected() -> None:
    card = ReelCard.model_validate({**SAMPLE_CARD, "title": "très " * 100, "key_points": ["x"] * 20})
    assert len(card.title) <= 90
    assert card.title.endswith("…")
    assert len(card.key_points) == 6


def test_tags_are_normalized() -> None:
    card = ReelCard.model_validate(
        {**SAMPLE_CARD, "tags": ["#Café", "café", "  Petit   Déj ", "", "a", "b", "c", "d"]}
    )
    assert card.tags[:2] == ["café", "petit déj"]
    assert len(card.tags) <= 6


def test_empty_optional_strings_become_none() -> None:
    card = ReelCard.model_validate({**SAMPLE_CARD, "action": "   ", "caution": ""})
    assert card.action is None
    assert card.caution is None


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ReelCard.model_validate({**SAMPLE_CARD, "details": {"kind": "horoscope"}})


def test_place_requires_at_least_one_place() -> None:
    with pytest.raises(ValidationError):
        ReelCard.model_validate({**SAMPLE_CARD, "details": {"kind": "place", "places": []}})


def test_json_schema_is_self_contained() -> None:
    schema = card_json_schema()
    text = json.dumps(schema)
    assert "$ref" not in text
    assert "$defs" not in text
    assert schema["type"] == "object"
    assert {"title", "tldr", "details"} <= set(schema["properties"])
    kinds = {variant["properties"]["kind"]["const"] for variant in schema["properties"]["details"]["oneOf"]}
    assert kinds == {"recipe", "workout", "place", "media", "product", "tip", "learning", "other"}

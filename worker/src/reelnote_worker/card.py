"""Schéma de la fiche générée par Claude.

La fiche a une partie commune (titre, résumé, points clés…) et une partie
`details` qui dépend du type de contenu (recette, sport, lieu…).

Les contraintes de longueur tronquent au lieu d'échouer : on préfère une fiche
légèrement raccourcie à une analyse rejetée. Seules les erreurs de structure
déclenchent une nouvelle demande au modèle.

Ce schéma est le contrat entre le worker et l'app : toute évolution
incompatible doit incrémenter PROMPT_VERSION (voir prompts.py) et être reflétée
dans web/lib/card.ts.
"""

from __future__ import annotations

import copy
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def _clip(max_len: int) -> BeforeValidator:
    def clip(value: object) -> object:
        if isinstance(value, str):
            value = " ".join(value.split())
            return value[: max_len - 1].rstrip() + "…" if len(value) > max_len else value
        return value

    return BeforeValidator(clip)


def _take(max_items: int) -> BeforeValidator:
    def take(value: object) -> object:
        return value[:max_items] if isinstance(value, list) else value

    return BeforeValidator(take)


def _empty_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


Text40 = Annotated[str, _clip(40)]
Text90 = Annotated[str, _clip(90)]
Text200 = Annotated[str, _clip(200)]
Text300 = Annotated[str, _clip(300)]
Text500 = Annotated[str, _clip(500)]
OptText60 = Annotated[str | None, BeforeValidator(_empty_to_none), _clip(60)]
OptText90 = Annotated[str | None, BeforeValidator(_empty_to_none), _clip(90)]
OptText120 = Annotated[str | None, BeforeValidator(_empty_to_none), _clip(120)]
OptText200 = Annotated[str | None, BeforeValidator(_empty_to_none), _clip(200)]
OptText300 = Annotated[str | None, BeforeValidator(_empty_to_none), _clip(300)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# --- Recette -----------------------------------------------------------------
class Ingredient(_Model):
    name: Text90
    quantity: OptText60 = Field(None, description="Quantité telle que mentionnée : '200 g', '2 c. à soupe'.")


class RecipeDetails(_Model):
    kind: Literal["recipe"]
    servings: int | None = Field(None, ge=1, le=100)
    prep_minutes: int | None = Field(None, ge=0, le=2880)
    cook_minutes: int | None = Field(None, ge=0, le=2880)
    ingredients: Annotated[list[Ingredient], _take(40)] = Field(default_factory=list)
    steps: Annotated[list[Text300], _take(25)] = Field(
        default_factory=list, description="Étapes dans l'ordre."
    )


# --- Sport -------------------------------------------------------------------
class Exercise(_Model):
    name: Text90
    sets: int | None = Field(None, ge=1, le=50)
    reps: OptText60 = Field(None, description="'12', '8-10', '30 s', 'max'…")
    rest_seconds: int | None = Field(None, ge=0, le=900)
    notes: OptText200 = None


class WorkoutDetails(_Model):
    kind: Literal["workout"]
    goal: OptText120 = None
    level: Literal["beginner", "intermediate", "advanced"] | None = None
    duration_minutes: int | None = Field(None, ge=1, le=600)
    equipment: Annotated[list[Text40], _take(12)] = Field(default_factory=list)
    exercises: Annotated[list[Exercise], _take(30)] = Field(default_factory=list)


# --- Lieu --------------------------------------------------------------------
class Place(_Model):
    name: Text90
    category: OptText60 = Field(None, description="restaurant, bar, café, hôtel, activité, nature, boutique…")
    address: OptText200 = None
    city: OptText60 = None
    country: OptText60 = None
    price_range: Literal["€", "€€", "€€€", "€€€€"] | None = None
    why: OptText200 = Field(None, description="Pourquoi y aller, en une phrase.")


class PlaceDetails(_Model):
    kind: Literal["place"]
    places: Annotated[list[Place], _take(15)] = Field(min_length=1)


# --- Livre, film, série… -----------------------------------------------------
class MediaItem(_Model):
    title: Text90
    media_type: Literal["book", "film", "series", "podcast", "music", "game", "other"]
    creator: OptText90 = Field(None, description="Auteur, réalisateur, artiste…")
    year: int | None = Field(None, ge=1000, le=2100)
    why: OptText200 = None


class MediaDetails(_Model):
    kind: Literal["media"]
    items: Annotated[list[MediaItem], _take(20)] = Field(min_length=1)


# --- Produit -----------------------------------------------------------------
class Product(_Model):
    name: Text90
    brand: OptText60 = None
    price: OptText60 = Field(None, description="Prix tel que mentionné, avec la devise.")
    where_to_buy: OptText120 = None
    why: OptText200 = None


class ProductDetails(_Model):
    kind: Literal["product"]
    products: Annotated[list[Product], _take(15)] = Field(min_length=1)


# --- Astuce ------------------------------------------------------------------
class TipDetails(_Model):
    kind: Literal["tip"]
    steps: Annotated[list[Text300], _take(12)] = Field(
        default_factory=list, description="Comment faire, étape par étape."
    )


# --- Apprentissage -----------------------------------------------------------
class Concept(_Model):
    term: Text90
    explanation: Text300


class Flashcard(_Model):
    question: Text200
    answer: Text300


class LearningDetails(_Model):
    kind: Literal["learning"]
    concepts: Annotated[list[Concept], _take(10)] = Field(default_factory=list)
    flashcards: Annotated[list[Flashcard], _take(8)] = Field(
        default_factory=list, description="Questions de révision pour ancrer l'apprentissage."
    )


# --- Autre -------------------------------------------------------------------
class OtherDetails(_Model):
    kind: Literal["other"]


Details = Annotated[
    RecipeDetails
    | WorkoutDetails
    | PlaceDetails
    | MediaDetails
    | ProductDetails
    | TipDetails
    | LearningDetails
    | OtherDetails,
    Field(discriminator="kind"),
]

CardKind = Literal["recipe", "workout", "place", "media", "product", "tip", "learning", "other"]


class ReelCard(_Model):
    title: Text90 = Field(description="Titre court et concret, sans clickbait.")
    emoji: Annotated[str, _clip(8)] = Field(description="Un seul emoji qui résume le contenu.")
    tldr: Text300 = Field(description="L'essentiel en une ou deux phrases.")
    key_points: Annotated[list[Text200], _take(6)] = Field(
        min_length=1, description="3 à 5 points à retenir, du plus au moins important."
    )
    action: OptText200 = Field(None, description="Une action concrète à tester, ou null.")
    tags: Annotated[list[str], _take(8)] = Field(
        default_factory=list, description="2 à 5 mots-clés en minuscules."
    )
    source_language: Annotated[str, _clip(8)] = Field(
        description="Langue de la vidéo, code ISO 639-1 ('fr', 'en'…)."
    )
    caution: OptText300 = Field(
        None,
        description="Si le reel affirme des choses discutables (santé, nutrition, médical, finance), "
        "ce qui mérite vérification en une phrase. Sinon null.",
    )
    details: Details

    @field_validator("tags", mode="after")
    @classmethod
    def _normalize_tags(cls, tags: list[str]) -> list[str]:
        seen: list[str] = []
        for tag in tags:
            clean = " ".join(tag.lstrip("#").lower().split())[:30]
            if clean and clean not in seen:
                seen.append(clean)
        return seen[:6]

    @property
    def kind(self) -> CardKind:
        return self.details.kind


# -----------------------------------------------------------------------------
# Schéma JSON pour l'outil Claude
# -----------------------------------------------------------------------------
_SCHEMA_NOISE = ("title", "$defs", "discriminator")


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    """Remplace les $ref par leur définition et retire les métadonnées inutiles.

    Les clés de `properties` sont des noms de champs (dont "title") : elles ne
    sont jamais filtrées, seules les métadonnées du schéma le sont.
    """
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        name = node["$ref"].split("/")[-1]
        merged = dict(_inline_refs(copy.deepcopy(defs[name]), defs))
        merged.update({k: _inline_refs(v, defs) for k, v in node.items() if k != "$ref"})
        return merged
    result: dict[str, Any] = {}
    for key, value in node.items():
        if key == "properties" and isinstance(value, dict):
            result[key] = {name: _inline_refs(prop, defs) for name, prop in value.items()}
        elif key not in _SCHEMA_NOISE:
            result[key] = _inline_refs(value, defs)
    return result


def card_json_schema() -> dict[str, Any]:
    """Schéma autonome (sans $ref) décrivant ReelCard, pour `input_schema`."""
    raw = ReelCard.model_json_schema()
    return dict(_inline_refs(raw, raw.get("$defs", {})))

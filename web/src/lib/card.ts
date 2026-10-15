/**
 * Types de la fiche, miroir de worker/src/reelnote_worker/card.py.
 * Toute évolution du schéma côté worker doit être reportée ici.
 */

export type CardKind = "recipe" | "workout" | "place" | "media" | "product" | "tip" | "learning" | "other";

export interface Ingredient {
  name: string;
  quantity: string | null;
}
export interface RecipeDetails {
  kind: "recipe";
  servings: number | null;
  prep_minutes: number | null;
  cook_minutes: number | null;
  ingredients: Ingredient[];
  steps: string[];
}

export interface Exercise {
  name: string;
  sets: number | null;
  reps: string | null;
  rest_seconds: number | null;
  notes: string | null;
}
export interface WorkoutDetails {
  kind: "workout";
  goal: string | null;
  level: "beginner" | "intermediate" | "advanced" | null;
  duration_minutes: number | null;
  equipment: string[];
  exercises: Exercise[];
}

export interface Place {
  name: string;
  category: string | null;
  address: string | null;
  city: string | null;
  country: string | null;
  price_range: string | null;
  why: string | null;
}
export interface PlaceDetails {
  kind: "place";
  places: Place[];
}

export type MediaType = "book" | "film" | "series" | "podcast" | "music" | "game" | "other";
export interface MediaItem {
  title: string;
  media_type: MediaType;
  creator: string | null;
  year: number | null;
  why: string | null;
}
export interface MediaDetails {
  kind: "media";
  items: MediaItem[];
}

export interface Product {
  name: string;
  brand: string | null;
  price: string | null;
  where_to_buy: string | null;
  why: string | null;
}
export interface ProductDetails {
  kind: "product";
  products: Product[];
}

export interface TipDetails {
  kind: "tip";
  steps: string[];
}

export interface LearningDetails {
  kind: "learning";
  concepts: { term: string; explanation: string }[];
  flashcards: { question: string; answer: string }[];
}

export interface OtherDetails {
  kind: "other";
}

export type CardDetails =
  | RecipeDetails
  | WorkoutDetails
  | PlaceDetails
  | MediaDetails
  | ProductDetails
  | TipDetails
  | LearningDetails
  | OtherDetails;

export interface ReelCard {
  title: string;
  emoji: string;
  tldr: string;
  key_points: string[];
  action: string | null;
  tags: string[];
  source_language: string;
  caution: string | null;
  details: CardDetails;
}

export interface KindInfo {
  label: string;
  plural: string;
  emoji: string;
}

export const KINDS: Record<CardKind, KindInfo> = {
  recipe: { label: "Recette", plural: "Recettes", emoji: "🍳" },
  workout: { label: "Sport", plural: "Sport", emoji: "💪" },
  place: { label: "Lieu", plural: "Lieux", emoji: "📍" },
  media: { label: "À voir, à lire", plural: "À voir, à lire", emoji: "📚" },
  product: { label: "Produit", plural: "Produits", emoji: "🛍️" },
  tip: { label: "Astuce", plural: "Astuces", emoji: "💡" },
  learning: { label: "Apprendre", plural: "Apprendre", emoji: "🧠" },
  other: { label: "Autre", plural: "Autres", emoji: "✨" },
};

export const KIND_ORDER: CardKind[] = ["recipe", "workout", "place", "media", "product", "tip", "learning", "other"];

export const MEDIA_TYPE_LABELS: Record<MediaType, string> = {
  book: "Livre",
  film: "Film",
  series: "Série",
  podcast: "Podcast",
  music: "Musique",
  game: "Jeu",
  other: "Autre",
};

export const LEVEL_LABELS = { beginner: "Débutant", intermediate: "Intermédiaire", advanced: "Avancé" } as const;

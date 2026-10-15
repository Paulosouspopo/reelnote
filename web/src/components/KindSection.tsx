"use client";

import { useMemo, useState } from "react";

import {
  LEVEL_LABELS,
  MEDIA_TYPE_LABELS,
  type CardDetails,
  type LearningDetails,
  type MediaDetails,
  type PlaceDetails,
  type ProductDetails,
  type RecipeDetails,
  type TipDetails,
  type WorkoutDetails,
} from "@/lib/card";
import { compact, formatMinutes } from "@/lib/format";
import { useLocalStorage } from "@/lib/useLocalStorage";

/** Partie spécifique de la fiche, selon le type de contenu. */
export function KindSection({ reelId, details }: { reelId: string; details: CardDetails }) {
  switch (details.kind) {
    case "recipe":
      return <Recipe reelId={reelId} details={details} />;
    case "workout":
      return <Workout details={details} />;
    case "place":
      return <Places details={details} />;
    case "media":
      return <Media details={details} />;
    case "product":
      return <Products details={details} />;
    case "tip":
      return <Tip details={details} />;
    case "learning":
      return <Learning details={details} />;
    case "other":
      return null;
  }
}

/** Ouvre la feuille de partage iOS : de là, Rappels, Notes, Messages… */
async function shareList(title: string, lines: string[]) {
  const text = lines.map((line) => `• ${line}`).join("\n");
  if (navigator.share) {
    await navigator.share({ title, text }).catch(() => undefined);
  } else {
    await navigator.clipboard.writeText(`${title}\n${text}`);
  }
}

/** Cases cochées mémorisées sur l'appareil (simple confort, non synchronisé). */
function useChecked(storageKey: string) {
  const [raw, write] = useLocalStorage(storageKey);
  const checked = useMemo(() => {
    try {
      return new Set<number>(raw ? (JSON.parse(raw) as number[]) : []);
    } catch {
      return new Set<number>();
    }
  }, [raw]);
  const toggle = (index: number) => {
    const next = new Set(checked);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    write(next.size ? JSON.stringify([...next]) : null);
  };
  return [checked, toggle] as const;
}

function Recipe({ reelId, details }: { reelId: string; details: RecipeDetails }) {
  const [checked, toggle] = useChecked(`reelnote:ingredients:${reelId}`);
  const facts = compact([
    details.servings ? `${details.servings} pers.` : null,
    formatMinutes(details.prep_minutes) && `Préparation ${formatMinutes(details.prep_minutes)}`,
    formatMinutes(details.cook_minutes) && `Cuisson ${formatMinutes(details.cook_minutes)}`,
  ]);

  return (
    <>
      {facts.length > 0 && (
        <div className="facts" style={{ marginTop: 24 }}>
          {facts.map((fact) => (
            <span key={fact} className="fact">
              {fact}
            </span>
          ))}
        </div>
      )}
      {details.ingredients.length > 0 && (
        <>
          <h2 className="section-title">Ingrédients</h2>
          <div className="panel">
            <ul className="checklist">
              {details.ingredients.map((ingredient, i) => (
                <li key={`${ingredient.name}-${i}`}>
                  <label>
                    <input type="checkbox" checked={checked.has(i)} onChange={() => toggle(i)} />
                    <span>{ingredient.name}</span>
                    {ingredient.quantity && <span className="quantity">{ingredient.quantity}</span>}
                  </label>
                </li>
              ))}
            </ul>
          </div>
          <button
            type="button"
            className="button button--quiet button--block"
            style={{ marginTop: 10 }}
            onClick={() =>
              shareList(
                "Liste de courses",
                details.ingredients.map((i) => (i.quantity ? `${i.name} (${i.quantity})` : i.name)),
              )
            }
          >
            Envoyer la liste de courses
          </button>
        </>
      )}
      {details.steps.length > 0 && (
        <>
          <h2 className="section-title">Étapes</h2>
          <ol className="steps">
            {details.steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </>
      )}
    </>
  );
}

function Workout({ details }: { details: WorkoutDetails }) {
  const facts = compact([
    details.goal,
    details.level ? LEVEL_LABELS[details.level] : null,
    formatMinutes(details.duration_minutes),
  ]);
  return (
    <>
      {facts.length > 0 && (
        <div className="facts" style={{ marginTop: 24 }}>
          {facts.map((fact) => (
            <span key={fact} className="fact">
              {fact}
            </span>
          ))}
        </div>
      )}
      {details.exercises.length > 0 && (
        <>
          <h2 className="section-title">Séance</h2>
          <ol className="steps">
            {details.exercises.map((exercise, i) => {
              const volume = [exercise.sets && `${exercise.sets} séries`, exercise.reps && `${exercise.reps} rép.`]
                .filter(Boolean)
                .join(" × ");
              return (
                <li key={`${exercise.name}-${i}`}>
                  <div>
                    <div className="item__name">{exercise.name}</div>
                    {volume && <div className="item__sub">{volume}</div>}
                    {exercise.rest_seconds ? <div className="item__sub">Repos {exercise.rest_seconds} s</div> : null}
                    {exercise.notes && <p className="item__why">{exercise.notes}</p>}
                  </div>
                </li>
              );
            })}
          </ol>
          <button
            type="button"
            className="button button--quiet button--block"
            style={{ marginTop: 14 }}
            onClick={() =>
              shareList(
                "Séance",
                details.exercises.map((e) => [e.name, e.sets && `${e.sets}×${e.reps ?? ""}`].filter(Boolean).join(" ")),
              )
            }
          >
            Envoyer la séance
          </button>
        </>
      )}
      {details.equipment.length > 0 && (
        <p className="small muted" style={{ marginTop: 14 }}>
          Matériel : {details.equipment.join(", ")}
        </p>
      )}
    </>
  );
}

function mapsUrl(query: string) {
  return `https://maps.apple.com/?q=${encodeURIComponent(query)}`;
}

function Places({ details }: { details: PlaceDetails }) {
  return (
    <>
      <h2 className="section-title">{details.places.length > 1 ? "Les adresses" : "L'adresse"}</h2>
      <ul className="item-list">
        {details.places.map((place, i) => {
          const where = [place.address, place.city, place.country].filter(Boolean).join(", ");
          return (
            <li key={`${place.name}-${i}`} className="item">
              <div className="item__head">
                <span className="item__name">{place.name}</span>
                {place.price_range && <span className="item__sub">{place.price_range}</span>}
              </div>
              {(place.category || where) && (
                <div className="item__sub">{[place.category, where].filter(Boolean).join(", ")}</div>
              )}
              {place.why && <p className="item__why">{place.why}</p>}
              <a
                className="link"
                href={mapsUrl([place.name, place.address, place.city].filter(Boolean).join(" "))}
                target="_blank"
                rel="noopener noreferrer"
                style={{ display: "inline-block", marginTop: 8 }}
              >
                Ouvrir dans Plans
              </a>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function Media({ details }: { details: MediaDetails }) {
  return (
    <>
      <h2 className="section-title">Recommandations</h2>
      <ul className="item-list">
        {details.items.map((item, i) => (
          <li key={`${item.title}-${i}`} className="item">
            <div className="item__head">
              <span className="item__name">{item.title}</span>
              <span className="item__sub">{MEDIA_TYPE_LABELS[item.media_type]}</span>
            </div>
            {(item.creator || item.year) && (
              <div className="item__sub">{[item.creator, item.year].filter(Boolean).join(", ")}</div>
            )}
            {item.why && <p className="item__why">{item.why}</p>}
          </li>
        ))}
      </ul>
    </>
  );
}

function Products({ details }: { details: ProductDetails }) {
  return (
    <>
      <h2 className="section-title">Produits</h2>
      <ul className="item-list">
        {details.products.map((product, i) => (
          <li key={`${product.name}-${i}`} className="item">
            <div className="item__head">
              <span className="item__name">{product.name}</span>
              {product.price && <span className="item__sub">{product.price}</span>}
            </div>
            {(product.brand || product.where_to_buy) && (
              <div className="item__sub">{[product.brand, product.where_to_buy].filter(Boolean).join(", ")}</div>
            )}
            {product.why && <p className="item__why">{product.why}</p>}
          </li>
        ))}
      </ul>
    </>
  );
}

function Tip({ details }: { details: TipDetails }) {
  if (details.steps.length === 0) return null;
  return (
    <>
      <h2 className="section-title">Comment faire</h2>
      <ol className="steps">
        {details.steps.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>
    </>
  );
}

function Learning({ details }: { details: LearningDetails }) {
  const [revealed, setRevealed] = useState<Set<number>>(new Set());
  return (
    <>
      {details.concepts.length > 0 && (
        <>
          <h2 className="section-title">Notions</h2>
          <ul className="item-list">
            {details.concepts.map((concept, i) => (
              <li key={`${concept.term}-${i}`} className="item">
                <div className="item__name">{concept.term}</div>
                <p className="item__why">{concept.explanation}</p>
              </li>
            ))}
          </ul>
        </>
      )}
      {details.flashcards.length > 0 && (
        <>
          <h2 className="section-title">Teste-toi</h2>
          <div className="stack">
            {details.flashcards.map((flashcard, i) => {
              const shown = revealed.has(i);
              return (
                <button
                  key={i}
                  type="button"
                  className="flashcard"
                  aria-expanded={shown}
                  onClick={() =>
                    setRevealed((current) => {
                      const next = new Set(current);
                      if (next.has(i)) next.delete(i);
                      else next.add(i);
                      return next;
                    })
                  }
                >
                  <span className="flashcard__side">{shown ? "Réponse" : "Question, touche pour voir la réponse"}</span>
                  <span className="flashcard__text">{shown ? flashcard.answer : flashcard.question}</span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}

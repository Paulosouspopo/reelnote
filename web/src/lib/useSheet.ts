import { useEffect, type RefObject } from "react";

const CLOSE_DISTANCE = 80;

/**
 * Comportement de feuille iOS pour un <dialog class="sheet"> : reste au-dessus du
 * clavier, se ferme en glissant vers le bas ou en touchant le fond.
 */
export function useSheet(ref: RefObject<HTMLDialogElement | null>) {
  useEffect(() => {
    const sheet = ref.current;
    if (!sheet) return;
    const viewport = window.visualViewport;

    // Safari ne réduit pas la page quand le clavier s'ouvre : on remonte la feuille de sa hauteur.
    const followKeyboard = () => {
      if (!viewport) return;
      const keyboard = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
      sheet.style.marginBottom = `${keyboard}px`;
    };

    let startY: number | null = null;
    let dragged = 0;
    const onStart = (e: TouchEvent) => {
      // Dans un champ, le geste sert à sélectionner ou faire défiler le texte.
      const touch = e.touches[0];
      if (!touch || (e.target as Element).closest("textarea, input, select")) return;
      startY = touch.clientY;
      dragged = 0;
      sheet.style.transition = "none";
    };
    const onMove = (e: TouchEvent) => {
      const touch = e.touches[0];
      if (startY === null || !touch) return;
      dragged = Math.max(0, touch.clientY - startY);
      sheet.style.transform = `translateY(${dragged}px)`;
    };
    const onEnd = () => {
      if (startY === null) return;
      startY = null;
      if (dragged > CLOSE_DISTANCE) sheet.close();
      else sheet.style.transition = "transform 0.2s ease-out";
      sheet.style.transform = "";
    };
    // Un clic sur le fond a pour cible le <dialog> lui-même, hors de sa boîte.
    const onClick = (e: MouseEvent) => {
      if (e.target !== sheet) return;
      const box = sheet.getBoundingClientRect();
      if (e.clientY < box.top || e.clientY > box.bottom || e.clientX < box.left || e.clientX > box.right) sheet.close();
    };

    viewport?.addEventListener("resize", followKeyboard);
    viewport?.addEventListener("scroll", followKeyboard);
    sheet.addEventListener("touchstart", onStart, { passive: true });
    sheet.addEventListener("touchmove", onMove, { passive: true });
    sheet.addEventListener("touchend", onEnd);
    sheet.addEventListener("touchcancel", onEnd);
    sheet.addEventListener("click", onClick);
    return () => {
      viewport?.removeEventListener("resize", followKeyboard);
      viewport?.removeEventListener("scroll", followKeyboard);
      sheet.removeEventListener("touchstart", onStart);
      sheet.removeEventListener("touchmove", onMove);
      sheet.removeEventListener("touchend", onEnd);
      sheet.removeEventListener("touchcancel", onEnd);
      sheet.removeEventListener("click", onClick);
    };
  }, [ref]);
}

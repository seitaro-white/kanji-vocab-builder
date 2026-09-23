"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const article = document.querySelector(".article");
  const controls = document.querySelectorAll("[data-furigana-mode]");
  const jlptToggle = document.querySelector("[data-jlpt-toggle]");
  if (!article) return;

  controls.forEach((control) => {
    control.addEventListener("click", () => {
      const mode = control.dataset.furiganaMode;
      article.classList.remove(
        "furigana-mode-unknown",
        "furigana-mode-all",
        "furigana-mode-none",
      );
      article.classList.add(`furigana-mode-${mode}`);
      controls.forEach((candidate) => {
        candidate.setAttribute("aria-pressed", String(candidate === control));
      });
    });
  });

  jlptToggle?.addEventListener("click", () => {
    const highlightKnown = jlptToggle.getAttribute("aria-pressed") !== "true";
    jlptToggle.setAttribute("aria-pressed", String(highlightKnown));
    article.classList.toggle("jlpt-highlight-unknown", !highlightKnown);
    article.classList.toggle("jlpt-highlight-all", highlightKnown);
  });
});

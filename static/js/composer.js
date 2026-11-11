// Enter sends; Shift+Enter, IME input and touch keyboards insert a newline instead.
const touchKeyboard = window.matchMedia("(pointer: coarse)");

function updateComposer(form) {
  const box = form.querySelector("textarea");
  box.style.height = "auto";
  box.style.height = `${box.scrollHeight}px`;
  form.querySelector("button[type=submit]").disabled = box.value.trim() === "";
  const count = form.querySelector("[data-count]");
  const max = Number(box.maxLength);
  count.hidden = box.value.length < max * 0.9;
  count.textContent = `${box.value.length.toLocaleString()} / ${max.toLocaleString()}`;
}

function scrollToLatest() {
  if (document.querySelector(".chat-messages li")) {
    document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight;
  }
}

document.addEventListener("input", (event) => {
  const form = event.target.closest("form.composer");
  if (form) updateComposer(form);
});

document.addEventListener("keydown", (event) => {
  const form = event.target.closest("form.composer");
  if (!form || event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  if (touchKeyboard.matches) return;
  event.preventDefault();
  if (!form.querySelector("button[type=submit]").disabled) form.requestSubmit();
});

// A plain (no-htmx) form disables Send itself, so a double click can't post twice.
document.addEventListener("submit", (event) => {
  const form = event.target.closest("form.composer:not([hx-post])");
  if (form) form.querySelector("button[type=submit]").disabled = true;
});

// htmx copies old attributes onto the new box while settling; a leftover height breaks the CSP.
document.addEventListener("htmx:beforeSwap", (event) => {
  event.detail.target.closest?.("form.composer")?.querySelector("textarea")?.removeAttribute("style");
});

// The swap brings a new box: focus it again.
document.addEventListener("htmx:afterSettle", (event) => {
  const form = event.target.closest?.("form.composer");
  if (!form) return;
  updateComposer(form);
  form.querySelector("textarea").focus();
  scrollToLatest();
});

for (const form of document.querySelectorAll("form.composer")) updateComposer(form);
scrollToLatest();

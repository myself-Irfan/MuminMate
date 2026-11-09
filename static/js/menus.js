// Menus are <details data-menu>: a click outside or Esc closes them, as users expect of a menu.
document.addEventListener("click", (event) => {
  for (const menu of document.querySelectorAll("details[data-menu][open]")) {
    if (!menu.contains(event.target)) menu.removeAttribute("open");
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  for (const menu of document.querySelectorAll("details[data-menu][open]")) {
    menu.removeAttribute("open");
    menu.querySelector("summary").focus();
  }
});

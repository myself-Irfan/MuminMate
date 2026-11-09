// Invoker Commands (commandfor/command) for browsers older than Baseline December 2025.
if (!("commandForElement" in HTMLButtonElement.prototype)) {
  document.addEventListener("click", (event) => {
    const button = event.target.closest("button[commandfor]");
    if (!button) return;
    const dialog = document.getElementById(button.getAttribute("commandfor"));
    const command = button.getAttribute("command");
    if (command === "show-modal") dialog.showModal();
    if (command === "close") dialog.close();
  });
}

// Pico's dialog is its own backdrop: a click on the dialog itself landed outside the panel.
document.addEventListener("click", (event) => {
  if (event.target instanceof HTMLDialogElement && event.target.open) event.target.close();
});

// A row's Delete link opens the shared confirm dialog; without JS it opens the confirm page.
const deleteDialog = document.getElementById("delete-dialog");
let deleteLink = null;

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-delete]");
  if (!link) return;
  event.preventDefault();
  deleteLink = link;
  link.closest("details").removeAttribute("open");
  deleteDialog.querySelector("[data-delete-title]").textContent = link.dataset.delete;
  deleteDialog.showModal();
});

deleteDialog.querySelector("[data-delete-confirm]").addEventListener("click", () => {
  const row = deleteLink.closest("li");
  htmx.ajax("POST", deleteLink.href, { source: row, target: row, swap: "outerHTML" });
  deleteDialog.close();
});

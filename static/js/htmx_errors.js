// htmx swaps nothing on a server error or a lost connection; say so instead of failing silently.
function showRequestError() {
  const main = document.querySelector("main");
  main.querySelector("[data-request-error]")?.remove();
  const banner = document.createElement("section");
  banner.className = "messages";
  banner.dataset.requestError = "";
  banner.setAttribute("aria-label", "Messages");
  const message = document.createElement("p");
  message.className = "error";
  message.setAttribute("role", "alert");
  message.textContent = "Something went wrong. Try again.";
  banner.append(message);
  main.prepend(banner);
}

document.addEventListener("htmx:responseError", showRequestError);
document.addEventListener("htmx:sendError", showRequestError);

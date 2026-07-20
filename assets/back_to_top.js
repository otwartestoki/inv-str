(function () {
  if (document.getElementById("back-to-top")) {
    return;
  }

  const style = document.createElement("style");
  style.textContent = `
    .back-to-top {
      position: fixed;
      right: 22px;
      bottom: 22px;
      z-index: 50;
      width: 44px;
      height: 44px;
      border: 1px solid #cfc7b8;
      border-radius: 999px;
      background: #15616d;
      color: #fff;
      box-shadow: 0 8px 20px rgba(20, 28, 28, 0.18);
      cursor: pointer;
      font: 700 22px/1 "Segoe UI", Arial, sans-serif;
      opacity: 0;
      pointer-events: none;
      transform: translateY(8px);
      transition: opacity 160ms ease, transform 160ms ease, background 160ms ease;
    }
    .back-to-top.is-visible {
      opacity: 1;
      pointer-events: auto;
      transform: translateY(0);
    }
    .back-to-top:hover {
      background: #0f4d56;
    }
    .back-to-top:focus-visible {
      outline: 3px solid #f2c94c;
      outline-offset: 3px;
    }
    @media (max-width: 720px) {
      .back-to-top {
        right: 14px;
        bottom: 14px;
      }
    }
  `;
  document.head.appendChild(style);

  const button = document.createElement("button");
  button.id = "back-to-top";
  button.className = "back-to-top";
  button.type = "button";
  button.setAttribute("aria-label", "Przewin do gory");
  button.title = "Do gory";
  button.textContent = "^";
  document.body.appendChild(button);

  function updateVisibility() {
    button.classList.toggle("is-visible", window.scrollY > 500);
  }

  button.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  window.addEventListener("scroll", updateVisibility, { passive: true });
  updateVisibility();
})();

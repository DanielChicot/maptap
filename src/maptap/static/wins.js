(function () {
  document.querySelectorAll(".seg").forEach((group) => {
    const buttons = group.querySelectorAll("button[aria-controls]");
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        buttons.forEach((other) => {
          const selected = other === button;
          other.setAttribute("aria-pressed", String(selected));
          document.getElementById(other.getAttribute("aria-controls")).hidden = !selected;
        });
      });
    });
  });
})();

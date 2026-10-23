// Ask for confirmation before submitting forms marked with data-confirm
document.querySelectorAll("form[data-confirm]").forEach(function (form) {
  form.addEventListener("submit", function (event) {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});

// Fade out flash messages after 5 seconds
setTimeout(function () {
  document.querySelectorAll(".flash").forEach(function (el) {
    el.style.transition = "opacity .6s";
    el.style.opacity = "0";
    setTimeout(function () { el.remove(); }, 700);
  });
}, 5000);

(function () {
  let lastFocusedElement = null;

  function injectModalHTML() {
    if (document.getElementById("confirmationModal")) return;

    const modalHTML = `
      <div class="modal fade" id="confirmationModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content border-0">
            <div class="modal-header bg-light">
              <h5 class="modal-title" id="confirmationModalTitle">Confirm</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div class="d-flex align-items-start gap-2">
                <i class="bi fs-3 text-primary" id="modal-icon"></i>
                <div><p class="mb-0" id="confirmationModalMessage">Are you sure?</p></div>
              </div>
            </div>
            <div class="modal-footer bg-light">
              <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Cancel</button>
              <a href="#" class="btn btn-primary btn-sm" id="confirmationModalConfirm">Confirm</a>
            </div>
          </div>
        </div>
      </div>`;
    document.body.insertAdjacentHTML("beforeend", modalHTML);
  }

  window.openConfirmationModal = function ({ title, message, confirmUrl, type = "info" }) {
    injectModalHTML();

    const modalEl = document.getElementById("confirmationModal");
    const modal = new bootstrap.Modal(modalEl);

    // Save current focus
    lastFocusedElement = document.activeElement;

    // Set modal content
    document.getElementById("confirmationModalTitle").textContent = title || "Confirm Action";
    document.getElementById("confirmationModalMessage").textContent = message || "Are you sure?";
    const confirmBtn = document.getElementById("confirmationModalConfirm");
    confirmBtn.href = confirmUrl || "#";

    // Set icon and button style
    const iconEl = document.getElementById("modal-icon");
    const iconMap = {
      info: "bi-info-circle-fill text-primary",
      danger: "bi-x-circle-fill text-danger",
      warning: "bi-exclamation-triangle-fill text-warning",
    };
    iconEl.className = `bi fs-3 ${iconMap[type] || iconMap.info}`;
    confirmBtn.className = `btn btn-sm ${type === "danger" ? "btn-danger" :
        type === "warning" ? "btn-warning" : "btn-primary"
      }`;

    // Accessibility fix: remove focus before hiding
    modalEl.addEventListener("hide.bs.modal", () => {
      if (document.activeElement && modalEl.contains(document.activeElement)) {
        document.activeElement.blur();
      }
    }, { once: true });

    // Restore focus after hidden
    modalEl.addEventListener("hidden.bs.modal", () => {
      if (lastFocusedElement) {
        lastFocusedElement.focus();
        lastFocusedElement = null;
      }
    }, { once: true });

    // Show modal
    setTimeout(() => modal.show(), 10);
  };
})();

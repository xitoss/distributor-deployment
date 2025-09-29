function showDialog(options) {
    const {
        text = "This is a message",
        title = "",
        theme = "info", // options: info, warning, danger, success
    } = options;

    const themes = {
        info: { headerClass: "bg-info text-white", icon: "bi-info-circle-fill" },
        success: { headerClass: "bg-success text-white", icon: "bi-check-circle-fill" },
        warning: { headerClass: "bg-warning text-dark", icon: "bi-exclamation-triangle-fill" },
        danger: { headerClass: "bg-danger text-white", icon: "bi-x-circle-fill" },
    };

    const themeConfig = themes[theme] || themes.info;

    // Remove existing dialog if any
    $("#genericDialog").remove();

    const dialogHTML = `
    <div class="modal fade" id="genericDialog" tabindex="-1" aria-labelledby="genericDialogLabel">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow">
                <div class="modal-header ${themeConfig.headerClass}">
                    <h5 class="modal-title mb-0" id="genericDialogLabel">
                        <i class="bi ${themeConfig.icon} me-2"></i>
                        ${title || "Notice"}
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p class="mb-0">${text}</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>`;

    $("body").append(dialogHTML);

    // Remove focus from any element before opening modal
    if (document.activeElement) document.activeElement.blur();

    const dialogElement = document.getElementById("genericDialog");
    const dialogModal = new bootstrap.Modal(dialogElement, { focus: false });
    dialogModal.show();

    // Optional: focus the Close button inside modal for accessibility
    const closeButton = dialogElement.querySelector(".btn-close");
    if (closeButton) closeButton.focus();

    // Blur active element BEFORE modal is hidden to prevent aria-hidden warning
    dialogElement.addEventListener('hide.bs.modal', function () {
        if (document.activeElement && dialogElement.contains(document.activeElement)) {
            document.activeElement.blur();
        }
    });
}
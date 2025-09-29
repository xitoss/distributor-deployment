$(document).ready(function () {
    $(".filter-form").submit(function (event) {

        $(this).find(".filter-input, .search-input").each(function () {
            if (!$(this).val().trim()) {
                $(this).removeAttr("name"); // Remove empty fields to clean up the URL
            }
        });
    });

    // Auto-submit when filter input changes
    $(".filter-input").change(function () {
        $(this).closest(".filter-form").submit();
    });
});
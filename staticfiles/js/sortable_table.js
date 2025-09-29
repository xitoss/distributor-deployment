$(document).ready(function () {
    $(".sortable-table").each(function () {
        let table = $(this);
        let sortOrder = {};

        table.find("th").each(function (index) {
            $(this).attr("data-sort", index); // Assign index-based sorting
            $(this).css("cursor", "pointer"); // Make headers clickable
            $(this).append(' <span class="sort-icon"><i class="bi bi-arrows-vertical"></i></span>'); // Default sort icon
        });

        table.find("th").click(function () {
            let tbody = table.find("tbody");
            let columnIndex = $(this).data("sort");
            let rows = tbody.find("tr").toArray();

            // Determine sort direction (toggle between ascending/descending)
            let order = sortOrder[columnIndex] === "asc" ? "desc" : "asc";
            sortOrder[columnIndex] = order;

            rows.sort(function (a, b) {
                let valA = $(a).children("td").eq(columnIndex).text().trim();
                let valB = $(b).children("td").eq(columnIndex).text().trim();

                // Handle numeric sorting
                if (!isNaN(valA) && !isNaN(valB)) {
                    valA = parseFloat(valA);
                    valB = parseFloat(valB);
                }

                return order === "asc" ? (valA > valB ? 1 : -1) : (valA < valB ? 1 : -1);
            });

            // Append sorted rows back to the tbody
            tbody.append(rows);

            // Reset all icons and update the clicked column
            table.find(".sort-icon i").removeClass("bi-arrow-up bi-arrow-down").addClass("bi-arrows-vertical"); // Reset all
            $(this).find(".sort-icon i").removeClass("bi-arrows-vertical").addClass(order === "asc" ? "bi-arrow-up" : "bi-arrow-down"); // Update clicked header
        });
    });
});

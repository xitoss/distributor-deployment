$(document).ready(function () {
    function updateTotalForms(formsetPrefix) {
        let count = $(`#${formsetPrefix} tbody tr.price-row`).length;
        $(`#id_${formsetPrefix}-TOTAL_FORMS`).val(count);
    }

    $("#add-price-row").click(function () {
        let formCount = parseInt($("#id_price_tiers-TOTAL_FORMS").val()); // Get the current form count
        let newRow = $("#empty-price-row").clone().removeClass("d-none").removeAttr("id");

        newRow.find("input, select").each(function () {
            let name = $(this).attr("name").replace("__prefix__", formCount);
            let id = $(this).attr("id").replace("__prefix__", formCount);
            $(this).attr({ name: name, id: id }).val("");
        });

        newRow.addClass("price-row"); // Ensure new row has the class
        $("#price-formset tbody").append(newRow);

        $("#id_price_tiers-TOTAL_FORMS").val(formCount + 1);
    });

    $(document).on("click", ".remove-price-row", function () {
        $(this).closest("tr").remove();
        updateTotalForms("price_tiers"); // Ensure correct count after removal
    });

    function updateTotalFormsUOM() {
        let count = $("#uom-formset tbody tr.uom-row").length;
        $("#id_uoms-TOTAL_FORMS").val(count);
    }

    $("#add-uom-row").click(function () {
        let formCount = parseInt($("#id_uoms-TOTAL_FORMS").val());
        let newRow = $("#empty-uom-row").clone().removeClass("d-none").removeAttr("id");

        newRow.find("input").each(function () {
            let name = $(this).attr("name").replace("__prefix__", formCount);
            let id = $(this).attr("id").replace("__prefix__", formCount);
            $(this).attr({ name: name, id: id }).val("");
        });

        newRow.addClass("uom-row");
        $("#uom-formset tbody").append(newRow);

        $("#id_uoms-TOTAL_FORMS").val(formCount + 1);
    });

    $(document).on("click", ".remove-uom-row", function () {
        $(this).closest("tr").remove();
        updateTotalFormsUOM();
    });
});

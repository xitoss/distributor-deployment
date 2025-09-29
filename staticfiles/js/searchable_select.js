function initializeSearchableSelect($select, placeholder = "Search...") {
    let $existingWrapper = $select.next(".searchable-wrapper");
    if ($existingWrapper.length) {
        $existingWrapper.remove();
    }

    let $wrapper = $('<div class="searchable-wrapper"></div>');
    let $input = $(`<input type="text" class="search-input" placeholder="${placeholder}">`);
    let $dropdown = $('<ul class="search-dropdown"></ul>');
    let $clearBtn = $('<span class="clear-btn">&times;</span>');

    $select.hide().after($wrapper);
    $wrapper.append($input).append($clearBtn).append($dropdown);

    function populateDropdown() {
        $dropdown.empty();
        $select.find("option").each(function () {
            let value = $(this).val();
            let text = $(this).text();
            if (value) {
                $dropdown.append(`<li data-value="${value}">${text}</li>`);
            }
        });

        // **Set pre-selected option when the page loads**
        let selectedValue = $select.val();  // Get the selected value from <select>
        if (selectedValue) {
            let selectedText = $select.find("option:selected").text();
            $input.val(selectedText);
            $clearBtn.show();
        }
    }

    function clear() {
        $input.val("");
        $select.val("").change();
        $clearBtn.hide();
    }

    populateDropdown();

    $input.on("focus", function () {
        $dropdown.show();
    });

    $input.on("input", function () {
        let searchTerm = $(this).val().toLowerCase();
        $dropdown.children("li").each(function () {
            let text = $(this).text().toLowerCase();
            $(this).toggle(text.includes(searchTerm));
        });
    });

    $dropdown.on("click", "li", function () {
        let selectedText = $(this).text();
        let selectedValue = $(this).data("value");
        $input.val(selectedText);
        $select.val(selectedValue).change();
        $dropdown.hide();
        $clearBtn.show();
    });

    $clearBtn.on("click", function () {
        clear();
        $dropdown.show();
    }).hide();

    $(document).on("click", function (e) {
        if (!$wrapper.is(e.target) && $wrapper.has(e.target).length === 0) {
            $dropdown.hide();
        }
    });

    let observer = new MutationObserver(() => {
        populateDropdown();
    });
    observer.observe($select[0], { childList: true });

    return { clear };
}

// Run automatically on all .searchable-select fields at page load
$(document).ready(function () {
    $(".searchable-select").each(function () {
        initializeSearchableSelect($(this));
    });
});

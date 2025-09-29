function initializeSearchableFilter($select, placeholder = "All") {
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

        // Preserve the empty option
        $select.find("option").each(function () {
            let value = $(this).val();
            let text = $(this).text();
            let isEmpty = value === "" || value === null;
            let displayText = isEmpty ? placeholder : text; // Show "All" for empty option

            $dropdown.append(`<li data-value="${value}">${displayText}</li>`);
        });

        let selectedValue = $select.val();
        if (selectedValue) {
            let selectedText = $select.find("option:selected").text();
            $input.val(selectedText);
            $clearBtn.show();
        } else {
            $input.val(placeholder);
        }
    }

    function clearInput() {
        $input.val(""); // Clear the input for typing
        $dropdown.show();
    }

    function resetToDefault() {
        let selectedValue = $select.val();
        if (selectedValue) {
            let selectedText = $select.find("option:selected").text();
            $input.val(selectedText);
            $clearBtn.show();
        } else {
            $input.val(placeholder);
            $clearBtn.hide();
        }
    }

    populateDropdown();

    $input.on("focus", function () {
        clearInput(); // Clear input when clicking the field
    });

    $input.on("blur", function () {
        setTimeout(() => {
            if ($input.val().trim() === "") {
                resetToDefault(); // Restore the selected value or placeholder
            }
        }, 200); // Delay to allow click selection
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
        $select.val("").change();
        resetToDefault();
        $dropdown.show();
    }).hide();

    $(document).on("click", function (e) {
        if (!$wrapper.is(e.target) && $wrapper.has(e.target).length === 0) {
            $dropdown.hide();
            if ($input.val().trim() === "") {
                resetToDefault(); // Restore the selected value or placeholder
            }
        }
    });

    let observer = new MutationObserver(() => {
        populateDropdown();
    });
    observer.observe($select[0], { childList: true });

    return { clear: resetToDefault };
}

// Apply to all select fields with .searchable-filter
$(document).ready(function () {
    $(".searchable-filter").each(function () {
        initializeSearchableFilter($(this));
    });
});
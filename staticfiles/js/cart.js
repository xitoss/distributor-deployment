function updateCartBadge(count) {
    const badge = document.querySelector("#cart-badge");
    if (count > 0) {
        if (!badge) {
            document.querySelector("#cart-link").innerHTML += ` <span id="cart-badge" class="badge bg-danger ms-1">${count}</span>`;
        } else {
            badge.textContent = count;
        }
    } else if (badge) {
        badge.remove();
    }
}

function add_to_cart(csrftoken, product_id) {
    $.ajax({
        url: `/api/cart/add/${product_id}/`,
        method: "POST",
        headers: { "X-CSRFToken": csrftoken },
        success: function (response) {
            showDialog({
                text: response.message,
                theme: "success"
            });

            updateCartBadge(response.cart_count);
        },
        error: function (xhr) {
            let resp = xhr.responseJSON;
            showDialog({
                text: resp?.message || "Something went wrong.",
                theme: "danger"
            });
        }
    });
}

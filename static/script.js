// ===================
// 共用功能函數
// ===================

// 顯示通知訊息
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.textContent = message;
    notification.onclick = () => notification.remove();

    let container = document.querySelector('.flash-messages');
    if (!container) {
        container = document.createElement('div');
        container.className = 'flash-messages';
        document.body.appendChild(container);
    }

    container.appendChild(notification);

    // 3秒後自動消失
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }
    }, 3000);
}

// 自動移除 flash 訊息
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.parentNode) {
                alert.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => alert.remove(), 300);
            }
        }, 4000);
    });
});

// ===================
// 菜單頁面專用功能
// ===================

// 購物車相關變數（只在菜單頁面使用）
let cart = {};
let menuItems = {};

// 修改商品數量
function changeQuantity(itemId, change) {
    if (!cart[itemId]) {
        cart[itemId] = 0;
    }

    const newQty = cart[itemId] + change;
    if (newQty >= 0) {
        cart[itemId] = newQty;
        const qtyElement = document.getElementById(`qty-${itemId}`);
        if (qtyElement) {
            qtyElement.textContent = newQty;
        }
        updateCartDisplay();
    }
}

// 更新購物車顯示
function updateCartDisplay() {
    let totalItems = 0;
    let totalPrice = 0;
    const cartItemsList = document.getElementById('cart-items-list');

    if (!cartItemsList) return; // 如果不是菜單頁面就返回

    // 清空購物車列表
    cartItemsList.innerHTML = '';

    // 重新建立購物車項目
    let hasItems = false;
    Object.entries(cart).forEach(([itemId, qty]) => {
        if (qty > 0) {
            hasItems = true;
            totalItems += qty;
            totalPrice += qty * menuItems[itemId].price;

            const cartItem = createCartItemElement(itemId, qty);
            cartItemsList.appendChild(cartItem);
        }
    });

    // 如果沒有商品，顯示空購物車訊息
    if (!hasItems) {
        cartItemsList.innerHTML = '<div class="empty-cart">購物車是空的，快去選擇美食吧！</div>';
    }

    // 更新統計資訊
    updateCartSummary(totalItems, totalPrice);
}

// 建立購物車項目元素
function createCartItemElement(itemId, qty) {
    const item = menuItems[itemId];
    const subtotal = qty * item.price;

    const cartItem = document.createElement('div');
    cartItem.className = 'cart-item';
    cartItem.innerHTML = `
        <div class="cart-item-info">
            <div class="cart-item-name">${item.name}</div>
            <div class="cart-item-price">NT$ ${item.price} × ${qty}</div>
        </div>
        <div class="cart-item-controls">
            <button class="cart-qty-btn" onclick="changeQuantity(${itemId}, -1)">-</button>
            <span class="cart-item-qty">${qty}</span>
            <button class="cart-qty-btn" onclick="changeQuantity(${itemId}, 1)">+</button>
            <div style="margin-left: 10px; font-weight: bold;">NT$ ${subtotal}</div>
        </div>
    `;

    return cartItem;
}

// 更新購物車摘要
function updateCartSummary(totalItems, totalPrice) {
    const elements = {
        totalItems: document.getElementById('total-items'),
        totalPrice: document.getElementById('total-price'),
        subtotal: document.getElementById('subtotal'),
        finalTotal: document.getElementById('final-total'),
        cartBadge: document.getElementById('cart-badge'),
        cartTotal: document.getElementById('cart-total'),
        checkoutBtn: document.getElementById('checkout-btn')
    };

    // 更新數量和價格顯示
    if (elements.totalItems) elements.totalItems.textContent = totalItems;
    if (elements.totalPrice) elements.totalPrice.textContent = totalPrice;
    if (elements.subtotal) elements.subtotal.textContent = totalPrice;
    if (elements.finalTotal) elements.finalTotal.textContent = totalPrice;

    // 更新購物車圖示徽章
    if (elements.cartBadge) {
        if (totalItems > 0) {
            elements.cartBadge.style.display = 'flex';
            elements.cartBadge.textContent = totalItems > 99 ? '99+' : totalItems;
        } else {
            elements.cartBadge.style.display = 'none';
        }
    }

    // 顯示/隱藏總計區域
    if (elements.cartTotal) {
        elements.cartTotal.style.display = totalItems > 0 ? 'block' : 'none';
    }

    // 啟用/禁用結帳按鈕
    if (elements.checkoutBtn) {
        elements.checkoutBtn.disabled = totalItems === 0;
    }
}

// 切換購物車顯示
function toggleCart() {
    const cartDetails = document.getElementById('cart-details');
    const chevron = document.getElementById('cart-chevron');

    if (cartDetails && chevron) {
        cartDetails.classList.toggle('open');
        chevron.classList.toggle('rotated');
    }
}

// 篩選菜單分類
function filterCategory(category) {
    // 更新按鈕狀態
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // 篩選菜單項目
    document.querySelectorAll('.menu-item').forEach(item => {
        if (category === 'all' || item.dataset.category === category) {
            item.style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
}

// 結帳功能
function checkout() {
    if (Object.values(cart).every(qty => qty === 0)) {
        showNotification('請選擇商品！', 'error');
        return;
    }

    const orderItems = [];
    let total = 0;

    Object.entries(cart).forEach(([itemId, qty]) => {
        if (qty > 0) {
            const item = menuItems[itemId];
            orderItems.push({
                menu_item_id: parseInt(itemId),
                quantity: qty,
                unit_price: item.price,
                subtotal: qty * item.price
            });
            total += qty * item.price;
        }
    });

    submitOrder({
        line_user_id: 'web_user_' + Date.now(),
        customer_name: '網頁用戶',
        total_amount: total,
        delivery_type: 'takeout',
        items: orderItems
    });
}

// 提交訂單
async function submitOrder(orderData) {
    try {
        const response = await fetch('/api/orders', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(orderData)
        });

        const result = await response.json();

        if (result.success) {
            showNotification('訂單建立成功！訂單編號：#' + result.order_id, 'success');

            // 清空購物車
            Object.keys(cart).forEach(key => {
                cart[key] = 0;
                const qtyElement = document.getElementById(`qty-${key}`);
                if (qtyElement) {
                    qtyElement.textContent = 0;
                }
            });

            updateCartDisplay();

            // 關閉購物車
            const cartDetails = document.getElementById('cart-details');
            const chevron = document.getElementById('cart-chevron');
            if (cartDetails && chevron) {
                cartDetails.classList.remove('open');
                chevron.classList.remove('rotated');
            }
        } else {
            showNotification('訂單建立失敗，請稍後再試', 'error');
        }
    } catch (error) {
        console.error('提交訂單失敗:', error);
        showNotification('網路錯誤，請稍後再試', 'error');
    }
}

// ===================
// 後台管理專用功能
// ===================

// 更新訂單狀態
async function updateStatus(orderId, newStatus) {
    try {
        const response = await fetch(`/api/orders/${orderId}/status`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ status: newStatus })
        });

        const result = await response.json();

        if (result.success) {
            showNotification('訂單狀態更新成功！', 'success');
            setTimeout(() => {
                location.reload();
            }, 1000);
        } else {
            showNotification('更新失敗: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('更新狀態失敗:', error);
        showNotification('網路錯誤，請稍後再試', 'error');
    }
}

// 篩選訂單
function filterOrders(filter) {
    // 更新按鈕狀態
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // 篩選訂單項目
    const orderCards = document.querySelectorAll('.order-card');
    let visibleCount = 0;

    orderCards.forEach(card => {
        const status = card.dataset.status;
        if (filter === 'all' || status === filter) {
            card.style.display = 'block';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });

    // 如果沒有符合條件的訂單，顯示提示
    const ordersList = document.getElementById('ordersList');
    const existingNoResults = document.querySelector('.no-results');

    if (visibleCount === 0 && !existingNoResults && ordersList) {
        const noResults = document.createElement('div');
        noResults.className = 'no-results no-orders';
        noResults.innerHTML = `
            <h3>🔍 沒有找到相關訂單</h3>
            <p>請嘗試其他篩選條件</p>
        `;
        ordersList.appendChild(noResults);
    } else if (visibleCount > 0 && existingNoResults) {
        existingNoResults.remove();
    }
}
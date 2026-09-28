// Инициализация Telegram Web App
const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// Применяем тему Telegram
if (tg.colorScheme === 'dark') {
    document.body.style.background = '#0f0f1e';
}

let cart = [];
let currentCategory = '';

// Эмодзи для категорий
const categoryEmojis = {
    'Одноразки': '💨',
    'Под-системы': '🔋',
    'Жидкость': '💧',
    'Расходники': '⚙️',
    'Жевательный табак': '',
    'Кальяны': ''
};

// Эмодзи для товаров (заглушка)
const productEmoji = '📦';

// ========== ЗАГРУЗКА КАТЕГОРИЙ ==========
async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        const categories = await response.json();
        
        const grid = document.getElementById('categories-grid');
        
        if (categories.length === 0) {
            grid.innerHTML = '<div class="loading">Категории не найдены</div>';
            return;
        }
        
        grid.innerHTML = categories.map(cat => {
            const emoji = categoryEmojis[cat.name] || '📦';
            return `
                <div class="category-card" onclick="openCategory('${cat.name}')">
                    <div class="emoji">${emoji}</div>
                    <div class="name">${cat.name}</div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Ошибка загрузки категорий:', error);
        document.getElementById('categories-grid').innerHTML = 
            '<div class="loading">Ошибка загрузки. Проверьте соединение.</div>';
    }
}

// ========== ОТКРЫТЬ КАТЕГОРИЮ ==========
async function openCategory(category) {
    currentCategory = category;
    document.getElementById('category-title').textContent = category;
    showPage('category-page');
    
    const grid = document.getElementById('products-grid');
    grid.innerHTML = '<div class="loading">Загрузка товаров...</div>';
    
    try {
        const response = await fetch(`/api/products/${encodeURIComponent(category)}`);
        const products = await response.json();
        
        if (products.length === 0) {
            grid.innerHTML = '<div class="loading">Товары не найдены</div>';
            return;
        }
        
        grid.innerHTML = products.map(p => `
            <div class="product-card">
                <div class="img-placeholder">
                    ${productEmoji}
                    <span class="favorite" onclick="toggleFavorite(this, event)"></span>
                </div>
                <div class="info">
                    <div class="name">${p.name}</div>
                    <div class="desc">${p.description}</div>
                    <div class="price">${p.price} ₽</div>
                    <button class="add-to-cart-btn" onclick="addToCart(${p.id}, '${p.name.replace(/'/g, "\\'")}', ${p.price})">
                        Добавить в корзину
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Ошибка загрузки товаров:', error);
        grid.innerHTML = '<div class="loading">Ошибка загрузки товаров</div>';
    }
}

// ========== КОРЗИНА ==========
function addToCart(id, name, price) {
    const existing = cart.find(item => item.id === id);
    if (existing) {
        existing.quantity++;
    } else {
        cart.push({ id, name, price, quantity: 1 });
    }
    
    // Вибрация (если поддерживается)
    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }
    
    showToast(`✅ ${name} добавлен в корзину`);
    updateCartBadge();
}

function showCart() {
    const container = document.getElementById('cart-items');
    
    if (cart.length === 0) {
        container.innerHTML = '<div class="empty-cart">🛒<br><br>Корзина пуста<br><br>Добавьте товары из каталога</div>';
    } else {
        container.innerHTML = cart.map(item => `
            <div class="cart-item">
                <div class="emoji">${productEmoji}</div>
                <div class="info">
                    <div class="name">${item.name}</div>
                    <div class="price">${item.price} ₽</div>
                </div>
                <div class="qty-controls">
                    <button class="qty-btn" onclick="changeQty(${item.id}, -1)">−</button>
                    <span class="qty-value">${item.quantity}</span>
                    <button class="qty-btn" onclick="changeQty(${item.id}, 1)">+</button>
                </div>
            </div>
        `).join('');
    }
    
    updateTotal();
    showPage('cart-page');
}

function changeQty(id, delta) {
    const item = cart.find(i => i.id === id);
    if (item) {
        item.quantity += delta;
        if (item.quantity <= 0) {
            cart = cart.filter(i => i.id !== id);
        }
        showCart();
        updateCartBadge();
        
        if (tg.HapticFeedback) {
            tg.HapticFeedback.selectionChanged();
        }
    }
}

function updateTotal() {
    const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
    document.getElementById('total-price').textContent = total;
}

function updateCartBadge() {
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    // Можно добавить бейдж на иконку корзины, если она есть в header
    console.log(`Товаров в корзине: ${totalItems}`);
}

// ========== ОФОРМЛЕНИЕ ЗАКАЗА ==========
function checkout() {
    if (cart.length === 0) {
        showToast(' Корзина пуста');
        return;
    }
    
    const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
    const data = {
        type: 'order',
        items: cart,
        total: total
    };
    
    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }
    
    // Отправляем данные боту
    tg.sendData(JSON.stringify(data));
}

// ========== НАВИГАЦИЯ ==========
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
    window.scrollTo(0, 0);
}

function goHome() {
    showPage('home-page');
}

function showProfile() {
    showToast('👤 Профиль в разработке');
}

function toggleFavorite(element, event) {
    event.stopPropagation();
    if (element.textContent === '') {
        element.textContent = '❤️';
        showToast('❤️ Добавлено в избранное');
    } else {
        element.textContent = '🤍';
    }
    
    if (tg.HapticFeedback) {
        tg.HapticFeedback.selectionChanged();
    }
}

// ========== УВЕДОМЛЕНИЯ ==========
function showToast(message) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.remove(), 2000);
}

// ========== ПОИСК ==========
document.getElementById('search-input')?.addEventListener('input', function(e) {
    const query = e.target.value.toLowerCase();
    // Здесь можно добавить логику поиска по товарам
    console.log('Поиск:', query);
});

// ========== ЗАПУСК ==========
loadCategories();
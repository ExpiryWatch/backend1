import { request, openForm, editProduct, openDeleteDialog } from './stock-form.js';

const list = document.querySelector('.products__list');
const count = document.querySelector('.products__count');
const pageError = document.querySelector('#stock-page-error');
const retryButton = document.querySelector('#stock-retry');
const loadingMessage = document.querySelector('#stock-loading');
const emptyStock = document.querySelector('#empty-stock');
const emptySearch = document.querySelector('#empty-search');
const search = document.querySelector('.products__search');
const status = document.querySelector('.products__filter');
const category = document.querySelector('.products__category');
const location = document.querySelector('.products__location');
const sort = document.querySelector('.products__sort');
const order = document.querySelector('.products__order');
let generation = 0;

function referenceOptions(select, values) {
    const selected = select.value;
    select.replaceChildren(select.options[0]);
    for (const value of values) select.add(new Option(value.name, value.id));
    if (Array.from(select.options).some(option => option.value === selected)) {
        select.value = selected;
    }
}

function textElement(tag, text, className = '') {
    const element = document.createElement(tag);
    element.textContent = text;
    element.className = className;
    return element;
}

function productCard(product, categories, locations) {
    const card = document.createElement('article');
    card.className = 'product-card';
    card.dataset.id = product.id;
    card.append(textElement('h3', product.name));
    card.append(textElement('p', `${product.quantity} ${product.unit}`, 'product-card__quantity'));
    card.append(textElement('p', categories.get(product.category_id) ?? 'Без категории'));
    card.append(textElement('p', locations.get(product.storage_location_id) ?? 'Без места хранения'));
    const expiry = textElement('p', 'Срок не указан');
    if (product.expiry_date) {
        expiry.textContent = 'Годен до ';
        const time = textElement('time', product.expiry_date.split('-').reverse().join('.'));
        time.dateTime = product.expiry_date;
        expiry.append(time);
    }
    card.append(expiry);
    if (product.days_left !== null) {
        card.append(textElement('p', `Дней до окончания срока: ${product.days_left}`));
    }
    const footer = textElement('div', '', 'product-card__footer');
    const modifier = { expiring_soon: 'soon', expired: 'expired', no_date: 'none' }[product.status];
    footer.append(textElement('span', product.status_label,
        'product-card__status' + (modifier ? ` product-card__status--${modifier}` : '')));
    const actions = textElement('div', '', 'product-card__actions');
    const edit = textElement('button', 'Редактировать', 'product-card__edit');
    edit.type = 'button';
    edit.addEventListener('click', () => editProduct(product.id, edit));
    const remove = textElement('button', 'Удалить', 'product-card__delete');
    remove.type = 'button';
    remove.addEventListener('click', () => openDeleteDialog(product));
    actions.append(edit, remove);
    footer.append(actions);
    card.append(footer);
    return card;
}

async function loadProducts() {
    const current = ++generation;
    const params = new URLSearchParams({ q: search.value.trim(), sort: sort.value, order: order.value });
    for (const [name, select] of [['status', status], ['category_id', category], ['storage_location_id', location]]) {
        if (select.value !== 'all') params.set(name, select.value);
    }
    list.setAttribute('aria-busy', 'true');
    loadingMessage.hidden = false;
    retryButton.hidden = true;
    retryButton.disabled = true;
    pageError.textContent = '';
    try {
        const [products, stats, categories, locations] = await Promise.all([
            request('/inventory/?' + params), request('/stats/'),
            request('/categories/'), request('/storage-locations/')
        ]);
        if (current !== generation) return;
        referenceOptions(category, categories);
        referenceOptions(location, locations);
        referenceOptions(document.querySelector('[name="category_id"]'), categories);
        referenceOptions(document.querySelector('[name="storage_location_id"]'), locations);
        const categoryNames = new Map(categories.map(item => [item.id, item.name]));
        const locationNames = new Map(locations.map(item => [item.id, item.name]));
        list.replaceChildren(...products.map(product => productCard(product, categoryNames, locationNames)));
        for (const value of document.querySelectorAll('[data-stat]')) {
            value.textContent = stats[value.dataset.stat];
        }
        count.textContent = `${products.length} из ${stats.total}`;
        emptyStock.hidden = stats.total > 0;
        emptySearch.hidden = stats.total === 0 || products.length > 0;
        document.querySelectorAll('.add-button:not(#stock-retry)').forEach(button => { button.disabled = false; });
    } catch (error) {
        if (current !== generation) return;
        pageError.textContent = error instanceof TypeError
            ? 'Не удалось связаться с сервером. Проверьте запуск приложения и повторите действие.'
            : error.message;
        count.textContent = 'Не удалось обновить список';
        retryButton.hidden = false;
        emptyStock.hidden = true;
        emptySearch.hidden = true;
    } finally {
        if (current === generation) {
            list.setAttribute('aria-busy', 'false');
            loadingMessage.hidden = true;
            retryButton.disabled = false;
        }
    }
}

for (const button of document.querySelectorAll('.add-button:not(#stock-retry)')) {
    button.disabled = true;
    if (button.id !== 'stock-add') button.addEventListener('click', () => openForm());
}
search.addEventListener('input', loadProducts);
retryButton.addEventListener('click', loadProducts);
for (const select of [status, category, location, sort, order]) {
    select.addEventListener('change', loadProducts);
}
document.addEventListener('stocks-changed', loadProducts);
window.addEventListener('focus', loadProducts);
// Обновляем рассчитанные сервером статусы, если страница открыта при смене дня.
setInterval(() => { if (!document.hidden) loadProducts(); }, 60000);
loadProducts();

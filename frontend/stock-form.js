const panel = document.querySelector('#stock-panel');
const form = document.querySelector('#stock-form');
const title = document.querySelector('#stock-title');
const description = document.querySelector('#stock-description');
const deleteDialog = document.querySelector('#stock-delete-dialog');
const deleteName = document.querySelector('#stock-delete-name');
const deleteError = document.querySelector('#stock-delete-error');
const deleteCancel = document.querySelector('#stock-delete-cancel');
const deleteConfirm = document.querySelector('#stock-delete-confirm');
const addButton = document.querySelector('#stock-add');
const saveButton = document.querySelector('#stock-save');
const closeButton = document.querySelector('#stock-close');
const cancelButton = document.querySelector('#stock-cancel');
const statusMessage = document.querySelector('#stock-status');
const pageError = document.querySelector('#stock-page-error');
const formError = document.querySelector('#stock-form-error');

const fields = [
  'name', 'quantity', 'unit', 'category_id', 'storage_location_id',
  'purchase_date', 'expiry_date', 'comment'
];

let editingId = null;
let saving = false;

const UPDATE_METHOD = 'PATCH';
let deletingId = null;
let deleting = false;

export async function request(path = '/inventory/', options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get('content-type') ?? '';
  const data = contentType.includes('json') ? await response.json() : null;

  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === 'string'
      ? detail
      : 'Не удалось выполнить запрос (' + response.status + ').';
    const error = new Error(message);
    error.detail = data?.errors ?? detail;
    throw error;
  }

  return data;
}

function productPath(id) {
  return `/inventory/${encodeURIComponent(id)}`;
}

function setFieldError(name, message) {
  const input = form.elements.namedItem(name);
  const output = document.getElementById(`error-${name}`);

  output.textContent = message;

  if (message) {
    input.setAttribute('aria-invalid', 'true');
  } else {
    input.removeAttribute('aria-invalid');
  }
}

function clearErrors() {
  formError.textContent = '';

  for (const name of fields) {
    setFieldError(name, '');
  }
}

function errorMessage(error) {
  if (error instanceof TypeError) {
    return 'Не удалось выполнить операцию. Попробуйте ещё раз.';
  }

  if (typeof error.detail?.message === 'string') {
    return error.detail.message;
  }

  return error.message || 'Не удалось выполнить операцию.';
}

function showSaveError(error) {
  // FastAPI обычно возвращает detail: [{ loc: ["body", "quantity"], msg: "..." }].
  if (!Array.isArray(error.detail) || error.detail.length === 0) {
    formError.textContent = errorMessage(error);
    return;
  }

  const generalMessages = [];
  let firstField = null;

  for (const issue of error.detail) {
    const location = Array.isArray(issue?.loc) ? issue.loc : [];
    const fieldName = location[1];
    const message = typeof issue === 'string'
      ? issue
      : issue?.msg || 'Проверь введённое значение.';

    if (location[0] === 'body' && fields.includes(fieldName)) {
      const output = document.getElementById('error-' + fieldName);
      const previous = output.textContent;
      setFieldError(fieldName, previous ? previous + '\n' + message : message);
      firstField ??= fieldName;
    } else {
      generalMessages.push(message);
    }
  }

  formError.textContent = generalMessages.join(' ');
  if (firstField) {
    form.elements.namedItem(firstField).focus();
  }
}

function loadProducts() {
  document.dispatchEvent(new Event('stocks-changed'));
}

function fillField(name, value) {
  const input = form.elements.namedItem(name);
  const text = value == null ? '' : String(value);

  // Сохраняем значение, если его пока нет среди временных вариантов HTML.
  if (input instanceof HTMLSelectElement && text) {
    const exists = Array.from(input.options).some((option) => option.value === text);
    if (!exists) {
      const option = new Option(text, text);
      option.dataset.savedValue = '';
      input.add(option);
    }
  }

  input.value = text;
}

export function openForm(product = null, id = null) {
  editingId = id;
  statusMessage.textContent = '';

  for (const option of form.querySelectorAll('[data-saved-value]')) {
    option.remove();
  }

  form.reset();
  clearErrors();

  title.textContent = product ? 'Редактировать продукт' : 'Добавить продукт';
  description.firstChild.textContent = product
    ? 'Измени информацию о продукте '
    : 'Заполни информацию о новом продукте ';
  saveButton.textContent = product ? 'Сохранить изменения' : 'Сохранить продукт';

  if (product) {
    for (const name of fields) {
      fillField(name, product[name]);
    }
  }

  if (!panel.open) {
    panel.showModal();
  }
}

export async function editProduct(id, button) {
  pageError.textContent = '';
  button.disabled = true;

  try {
    const product = await request(productPath(id));

    if (!product || typeof product !== 'object' || Array.isArray(product)) {
      throw new Error('Сервер не вернул данные позиции.');
    }

    if (!panel.open && !deleteDialog.open) {
      openForm(product, id);
    }
  } catch (error) {
    pageError.textContent = errorMessage(error);
  } finally {
    button.disabled = false;
  }
}

function readProduct() {
  const values = Object.fromEntries(new FormData(form));

  return {
    name: values.name.trim(),
    quantity: values.quantity === '' ? null : Number(values.quantity),
    unit: values.unit,
    category_id: values.category_id ? Number(values.category_id) : null,
    storage_location_id: values.storage_location_id ? Number(values.storage_location_id) : null,
    purchase_date: values.purchase_date || null,
    expiry_date: values.expiry_date || null,
    comment: values.comment.trim() || null
  };
}

function validateProduct(product) {
  const errors = {};

  if (!product.name) {
    errors.name = 'Укажи наименование продукта';
  }

  if (form.elements.quantity.validity.badInput) {
    errors.quantity = 'Укажи число';
  } else if (product.quantity === null) {
    errors.quantity = 'Укажи количество';
  } else if (!Number.isFinite(product.quantity) || product.quantity <= 0) {
    errors.quantity = 'Количество должно быть больше нуля.';
  }

  if (form.elements.purchase_date.validity.badInput) {
    errors.purchase_date = 'Укажи корректную дату приобретения.';
  }

  if (form.elements.expiry_date.validity.badInput) {
    errors.expiry_date = 'Укажи корректный срок годности.';
  } else if (
    product.purchase_date &&
    product.expiry_date &&
    product.expiry_date < product.purchase_date
  ) {
    errors.expiry_date = 'Срок годности не может быть раньше даты приобретения.';
  }

  for (const [name, message] of Object.entries(errors)) {
    setFieldError(name, message);
  }

  const firstField = Object.keys(errors)[0];
  if (firstField) {
    form.elements.namedItem(firstField).focus();
    return false;
  }

  return true;
}

function setSaving(value) {
  saving = value;
  saveButton.disabled = value;
  closeButton.disabled = value;
  cancelButton.disabled = value;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (saving) return;

  clearErrors();
  const product = readProduct();
  if (!validateProduct(product)) return;

  const isEditing = editingId !== null;
  const path = isEditing ? productPath(editingId) : '/inventory/';

  setSaving(true);

  try {
    await request(path, {
      method: isEditing ? UPDATE_METHOD : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(product)
    });

    panel.close();
    addButton.focus();
    statusMessage.textContent = isEditing
      ? 'Изменения сохранены.'
      : 'Продукт добавлен.';

    await loadProducts();
  } catch (error) {
    showSaveError(error);
  } finally {
    setSaving(false);
  }
});

addButton.addEventListener('click', () => {
  if (!saving && !deleting) openForm();
});

closeButton.addEventListener('click', () => panel.close());
cancelButton.addEventListener('click', () => panel.close());

panel.addEventListener('cancel', (event) => {
  if (saving) event.preventDefault();
});

export function openDeleteDialog(product) {
  deletingId = product.id;
  statusMessage.textContent = '';
  deleteError.textContent = '';
  deleteName.textContent = product.name;
  deleteDialog.showModal();
}

deleteCancel.addEventListener('click', () => deleteDialog.close());

deleteDialog.addEventListener('cancel', (event) => {
  if (deleting) event.preventDefault();
});

deleteConfirm.addEventListener('click', async () => {
  if (deleting || deletingId === null) return;

  deleting = true;
  deleteConfirm.disabled = true;
  deleteCancel.disabled = true;
  deleteError.textContent = '';

  try {
    await request(productPath(deletingId), { method: 'DELETE' });
    deleteDialog.close();
    await loadProducts();
    addButton.focus();
    statusMessage.textContent = 'Продукт удалён.';
  } catch (error) {
    deleteError.textContent = errorMessage(error);
  } finally {
    deleting = false;
    deleteConfirm.disabled = false;
    deleteCancel.disabled = false;
  }
});


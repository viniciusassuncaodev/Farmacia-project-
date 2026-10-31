const loginPanel = document.querySelector('#login-panel');
const dashboard = document.querySelector('#dashboard');
const loginForm = document.querySelector('#login-form');
const loginMessage = document.querySelector('#login-message');
const logoutButton = document.querySelector('#logout-button');
const productForm = document.querySelector('#product-form');
const productRows = document.querySelector('#product-rows');
const categoryForm = document.querySelector('#category-form');
const categoryRows = document.querySelector('#category-rows');
const productMessage = document.querySelector('#product-message');
const listMessage = document.querySelector('#list-message');
const categoryMessage = document.querySelector('#category-message');
const categorySelect = document.querySelector('#product-category');
const cancelEditButton = document.querySelector('#cancel-edit');
const saveProductButton = document.querySelector('#save-product');
const saveCategoryButton = document.querySelector('#save-category');
let currentCategories = [];

async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });
  const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) showLogin();
    throw new Error(data.detail || 'Não foi possível concluir a operação.');
  }
  return data;
}

function showLogin(message = '') {
  dashboard.hidden = true;
  loginPanel.hidden = false;
  loginMessage.textContent = message;
}

function showDashboard() {
  loginPanel.hidden = true;
  dashboard.hidden = false;
  loadCategories();
  loadProducts();
}

function setMessage(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle('message-error', isError);
}

async function loadCategories() {
  try {
    const { items } = await apiRequest('/api/categories');
    currentCategories = items;
    categorySelect.replaceChildren();
    items.forEach((item) => {
      const option = document.createElement('option');
      option.value = item.slug;
      option.textContent = item.name;
      categorySelect.append(option);
    });
    renderCategoryRows(items);
    setMessage(categoryMessage, `${items.length} ${items.length === 1 ? 'categoria cadastrada' : 'categorias cadastradas'}.`);
  } catch (error) {
    setMessage(categoryMessage, error.message, true);
  }
}

function renderCategoryRows(items) {
  categoryRows.replaceChildren();
  if (!items.length) {
    const row = document.createElement('tr');
    const cell = addCell(row, 'Nenhuma categoria cadastrada.');
    cell.colSpan = 4;
    cell.className = 'empty-row';
    categoryRows.append(row);
    return;
  }

  items.forEach((category) => {
    const row = document.createElement('tr');
    addCell(row, category.name);
    addCell(row, category.slug);
    addCell(row, String(category.product_count));
    const actionsCell = document.createElement('td');
    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'admin-button secondary';
    editButton.dataset.slug = category.slug;
    editButton.textContent = 'Editar nome';
    actionsCell.append(editButton);
    row.append(actionsCell);
    categoryRows.append(row);
  });
}

function formatPrice(price) {
  return Number(price).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function addCell(row, value) {
  const cell = document.createElement('td');
  cell.textContent = value;
  row.append(cell);
  return cell;
}

function renderProductRows(items) {
  productRows.replaceChildren();
  if (!items.length) {
    const row = document.createElement('tr');
    const cell = addCell(row, 'Nenhum produto cadastrado.');
    cell.colSpan = 5;
    cell.className = 'empty-row';
    productRows.append(row);
    return;
  }

  items.forEach((product) => {
    const row = document.createElement('tr');
    const nameCell = addCell(row, product.name);
    const badges = document.createElement('span');
    badges.className = 'product-badges';
    if (product.is_demo) {
      const demoBadge = document.createElement('span');
      demoBadge.className = 'product-badge';
      demoBadge.textContent = 'DEMO';
      badges.append(demoBadge);
    }
    if (!product.active) {
      const inactiveBadge = document.createElement('span');
      inactiveBadge.className = 'product-badge inactive';
      inactiveBadge.textContent = 'INATIVO';
      badges.append(inactiveBadge);
    }
    if (badges.childElementCount) nameCell.append(badges);

    addCell(row, product.category);
    addCell(row, formatPrice(product.price));
    addCell(row, product.active ? 'Ativo' : 'Inativo');

    const actionsCell = document.createElement('td');
    const actions = document.createElement('div');
    actions.className = 'row-actions';
    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'admin-button secondary';
    editButton.dataset.action = 'edit';
    editButton.dataset.slug = product.slug;
    editButton.textContent = 'Editar';
    actions.append(editButton);
    if (product.active) {
      const deactivateButton = document.createElement('button');
      deactivateButton.type = 'button';
      deactivateButton.className = 'admin-button secondary';
      deactivateButton.dataset.action = 'deactivate';
      deactivateButton.dataset.slug = product.slug;
      deactivateButton.textContent = 'Desativar';
      actions.append(deactivateButton);
    }
    actionsCell.append(actions);
    row.append(actionsCell);
    productRows.append(row);
  });
}

async function loadProducts() {
  setMessage(listMessage, 'Carregando produtos...');
  try {
    const { items } = await apiRequest('/api/admin/products');
    renderProductRows(items);
    setMessage(listMessage, `${items.length} ${items.length === 1 ? 'produto' : 'produtos'} no catálogo.`);
  } catch (error) {
    setMessage(listMessage, error.message, true);
  }
}

function resetProductForm() {
  productForm.reset();
  document.querySelector('#product-slug').value = '';
  document.querySelector('#product-active').checked = true;
  document.querySelector('#product-demo').checked = true;
  document.querySelector('#form-title').textContent = 'Novo produto';
  saveProductButton.textContent = 'Salvar produto';
  cancelEditButton.hidden = true;
  setMessage(productMessage, '');
}

function resetCategoryForm() {
  categoryForm.reset();
  document.querySelector('#category-slug').value = '';
  document.querySelector('#category-title').textContent = 'Categorias';
  saveCategoryButton.textContent = 'Cadastrar categoria';
  document.querySelector('#cancel-category-edit').hidden = true;
  setMessage(categoryMessage, '');
}

function startCategoryEdit(category) {
  document.querySelector('#category-slug').value = category.slug;
  document.querySelector('#category-name').value = category.name;
  document.querySelector('#category-title').textContent = 'Editar categoria';
  saveCategoryButton.textContent = 'Salvar categoria';
  document.querySelector('#cancel-category-edit').hidden = false;
  setMessage(categoryMessage, `Identificador: ${category.slug}. Ele não muda ao editar o nome.`);
  categoryForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function startEdit(product) {
  document.querySelector('#product-slug').value = product.slug;
  document.querySelector('#product-name').value = product.name;
  categorySelect.value = product.category_slug;
  document.querySelector('#product-description').value = product.description;
  document.querySelector('#product-price').value = Number(product.price).toFixed(2);
  document.querySelector('#product-package').value = product.package_label;
  document.querySelector('#product-theme').value = product.visual_theme;
  document.querySelector('#product-demo').checked = product.is_demo;
  document.querySelector('#product-active').checked = product.active;
  document.querySelector('#form-title').textContent = 'Editar produto';
  saveProductButton.textContent = 'Salvar alterações';
  cancelEditButton.hidden = false;
  setMessage(productMessage, 'Confira a opção de demonstração antes de salvar.');
  document.querySelector('.product-form-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = loginForm.querySelector('button[type="submit"]');
  button.disabled = true;
  setMessage(loginMessage, 'Verificando acesso...');
  try {
    await apiRequest('/api/admin/login', {
      method: 'POST',
      body: JSON.stringify({
        username: document.querySelector('#login-username').value,
        password: document.querySelector('#login-password').value,
      }),
    });
    loginForm.reset();
    showDashboard();
  } catch (error) {
    setMessage(loginMessage, error.message, true);
  } finally {
    button.disabled = false;
  }
});

logoutButton.addEventListener('click', async () => {
  try {
    await apiRequest('/api/admin/logout', { method: 'POST' });
  } finally {
    showLogin('Você saiu do painel.');
  }
});

productForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  saveProductButton.disabled = true;
  const slug = document.querySelector('#product-slug').value;
  const payload = {
    name: document.querySelector('#product-name').value.trim(),
    category_slug: categorySelect.value,
    description: document.querySelector('#product-description').value.trim(),
    price: document.querySelector('#product-price').value,
    package_label: document.querySelector('#product-package').value.trim(),
    visual_theme: document.querySelector('#product-theme').value,
    is_demo: document.querySelector('#product-demo').checked,
    active: document.querySelector('#product-active').checked,
  };

  try {
    await apiRequest(slug ? `/api/admin/products/${encodeURIComponent(slug)}` : '/api/admin/products', {
      method: slug ? 'PUT' : 'POST',
      body: JSON.stringify(payload),
    });
    resetProductForm();
    setMessage(productMessage, slug ? 'Produto atualizado.' : 'Produto cadastrado.');
    await loadProducts();
  } catch (error) {
    setMessage(productMessage, error.message, true);
  } finally {
    saveProductButton.disabled = false;
  }
});

categoryForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  saveCategoryButton.disabled = true;
  const slug = document.querySelector('#category-slug').value;
  const payload = { name: document.querySelector('#category-name').value.trim() };
  try {
    await apiRequest(
      slug ? `/api/admin/categories/${encodeURIComponent(slug)}` : '/api/admin/categories',
      { method: slug ? 'PUT' : 'POST', body: JSON.stringify(payload) },
    );
    resetCategoryForm();
    await loadCategories();
    await loadProducts();
    setMessage(categoryMessage, slug ? 'Categoria atualizada.' : 'Categoria cadastrada.');
  } catch (error) {
    setMessage(categoryMessage, error.message, true);
  } finally {
    saveCategoryButton.disabled = false;
  }
});

categoryRows.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-slug]');
  if (!button) return;
  const category = currentCategories.find((item) => item.slug === button.dataset.slug);
  if (category) startCategoryEdit(category);
});

productRows.addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const productSlug = button.dataset.slug;
  const action = button.dataset.action;

  try {
    const { items } = await apiRequest('/api/admin/products');
    const product = items.find((item) => item.slug === productSlug);
    if (!product) return;
    if (action === 'edit') {
      startEdit(product);
      return;
    }
    if (action === 'deactivate' && window.confirm(`Desativar “${product.name}” na loja?`)) {
      await apiRequest(`/api/admin/products/${encodeURIComponent(productSlug)}`, { method: 'DELETE' });
      if (document.querySelector('#product-slug').value === productSlug) resetProductForm();
      await loadProducts();
      setMessage(listMessage, 'Produto desativado na loja.');
    }
  } catch (error) {
    setMessage(listMessage, error.message, true);
  }
});

document.querySelector('#cancel-edit').addEventListener('click', resetProductForm);
document.querySelector('#cancel-category-edit').addEventListener('click', resetCategoryForm);
document.querySelector('#refresh-categories').addEventListener('click', loadCategories);
document.querySelector('#new-product').addEventListener('click', () => {
  resetProductForm();
  document.querySelector('.product-form-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
});
document.querySelector('#refresh-products').addEventListener('click', loadProducts);

apiRequest('/api/admin/session')
  .then(showDashboard)
  .catch(() => showLogin());

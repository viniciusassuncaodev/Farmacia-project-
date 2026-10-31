const menuToggle = document.querySelector('#menu-toggle');
const navigation = document.querySelector('#primary-navigation');
const searchForm = document.querySelector('#search-form');
const searchInput = document.querySelector('#search-input');
const searchStatus = document.querySelector('#search-status');
const categoryList = document.querySelector('#category-list');
const catalogGrid = document.querySelector('#catalog-list');
const demoLabel = document.querySelector('#demo-label');
const catalogNote = document.querySelector('#catalog-note');

function normalizeText(value) {
  return value
    .toLocaleLowerCase('pt-BR')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

function createCatalogCard(product) {
  const card = document.createElement('article');
  card.className = 'catalog-card';
  card.dataset.search = `${product.name} ${product.description} ${product.category}`;

  const visual = document.createElement('div');
  visual.className = `catalog-visual visual-${product.visual_theme}`;
  const packageLabel = document.createElement('b');
  packageLabel.textContent = product.package_label;
  if (product.image_url) {
    visual.classList.add('has-product-image');
    const image = document.createElement('img');
    image.className = 'catalog-product-image';
    image.src = product.image_url;
    image.alt = product.name;
    visual.append(image, packageLabel);
  } else {
    visual.setAttribute('aria-hidden', 'true');
    const productName = document.createElement('span');
    productName.textContent = product.name;
    visual.append(productName, packageLabel);
  }

  const info = document.createElement('div');
  info.className = 'catalog-info';
  const category = document.createElement('span');
  category.className = 'catalog-category';
  category.textContent = product.category;
  const name = document.createElement('h3');
  name.textContent = product.name;
  const description = document.createElement('p');
  description.textContent = product.description;
  const price = document.createElement('strong');
  price.className = 'catalog-price';
  price.textContent = Number(product.price).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
  const link = document.createElement('a');
  link.href = '#unidades';
  link.className = 'catalog-link';
  link.append(document.createTextNode('Consultar na unidade '));
  const arrow = document.createElement('span');
  arrow.setAttribute('aria-hidden', 'true');
  arrow.textContent = '→';
  link.append(arrow);
  info.append(category, name, description, price, link);
  card.append(visual, info);
  return card;
}

function createCategoryCard(category) {
  const icons = {
    dermocosmeticos: 'sanitizer',
    'higiene-pessoal': 'shower',
    vitaminas: 'medication',
    beleza: 'spa',
    medicamentos: 'pill',
    'bebe-infantil': 'child_care',
    perfumaria: 'experiment',
  };
  const link = document.createElement('a');
  link.className = 'category';
  link.href = '#ofertas';
  const icon = document.createElement('span');
  icon.className = 'material-symbols-outlined icon';
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = icons[category.slug] ?? 'category';
  link.append(icon, document.createTextNode(category.name));
  return link;
}

async function loadCategoryTiles() {
  if (!categoryList) return;
  try {
    const response = await fetch('/api/categories');
    if (!response.ok) return;
    const { items } = await response.json();
    if (!Array.isArray(items)) return;
    categoryList.replaceChildren(...items.map(createCategoryCard));
    if (searchInput?.value) filterCategories(searchInput.value);
  } catch {
    // Mantém as categorias demonstrativas do HTML quando a API estiver indisponível.
  }
}

async function loadCatalog() {
  if (!catalogGrid) return;

  try {
    const response = await fetch('/api/products');
    if (!response.ok) return;
    const { items } = await response.json();
    if (!Array.isArray(items)) return;

    catalogGrid.replaceChildren(...items.map(createCatalogCard));
    const hasDemoItems = items.some((product) => product.is_demo);
    const onlyDemoItems = items.length > 0 && items.every((product) => product.is_demo);
    if (demoLabel) {
      demoLabel.hidden = !hasDemoItems;
      if (hasDemoItems && !onlyDemoItems) demoLabel.textContent = 'Inclui produtos demonstrativos';
    }
    if (catalogNote) catalogNote.hidden = !hasDemoItems;

    if (searchInput?.value) filterCategories(searchInput.value);
  } catch {
    // Mantém os cartões de demonstração do HTML se a API não estiver disponível.
  }
}

function setMenuOpen(isOpen) {
  navigation?.classList.toggle('open', isOpen);
  menuToggle?.setAttribute('aria-expanded', String(isOpen));
  menuToggle?.setAttribute('aria-label', isOpen ? 'Fechar menu' : 'Abrir menu');
}

menuToggle?.addEventListener('click', () => {
  setMenuOpen(menuToggle.getAttribute('aria-expanded') !== 'true');
});

navigation?.querySelectorAll('a').forEach((link) => {
  link.addEventListener('click', () => setMenuOpen(false));
});

function filterCategories(query) {
  const normalizedQuery = normalizeText(query.trim());
  let visibleCategories = 0;
  let visibleProducts = 0;

  categoryList?.querySelectorAll('.category').forEach((category) => {
    const matches = normalizeText(category.textContent).includes(normalizedQuery);
    category.hidden = !matches;
    if (matches) visibleCategories += 1;
  });

  catalogGrid?.querySelectorAll('.catalog-card').forEach((card) => {
    const searchableText = `${card.dataset.search ?? ''} ${card.textContent}`;
    const matches = normalizeText(searchableText).includes(normalizedQuery);
    card.hidden = !matches;
    if (matches) visibleProducts += 1;
  });

  if (searchStatus) {
    if (!normalizedQuery) {
      searchStatus.textContent = '';
    } else if (visibleCategories + visibleProducts === 0) {
      searchStatus.textContent = `Nenhum resultado encontrado para: ${query.trim()}.`;
    } else {
      const parts = [];
      if (visibleCategories) parts.push(`${visibleCategories} ${visibleCategories === 1 ? 'categoria' : 'categorias'}`);
      if (visibleProducts) parts.push(`${visibleProducts} ${visibleProducts === 1 ? 'produto' : 'produtos'}`);
      searchStatus.textContent = `Encontrados: ${parts.join(' e ')}.`;
    }
  }

  return visibleCategories + visibleProducts;
}

searchForm?.addEventListener('submit', (event) => {
  event.preventDefault();
  filterCategories(searchInput?.value ?? '');
  document.querySelector('#produtos')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

searchInput?.addEventListener('input', () => {
  filterCategories(searchInput.value);
});

loadCatalog();
loadCategoryTiles();

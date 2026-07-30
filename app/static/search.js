const searchBindings = [
  {
    selectId: 'player',
    inputId: 'player-search',
    listId: 'player-options',
    comparison: false
  },
  {
    selectId: 'compare',
    inputId: 'compare-search',
    listId: 'compare-options',
    comparison: true
  }
];

function normalizePlayerSearch(value) {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

function availableOptions(binding) {
  return [...document.getElementById(binding.selectId).options]
    .filter(option => option.value);
}

function refreshPlayerSearch(binding) {
  const list = document.getElementById(binding.listId);
  const select = document.getElementById(binding.selectId);
  const input = document.getElementById(binding.inputId);

  const items = availableOptions(binding).map(option => {
    const item = document.createElement('option');
    item.value = option.textContent;
    return item;
  });

  list.replaceChildren(...items);

  const selected = select.selectedOptions[0];

  input.value =
    selected && selected.value
      ? selected.textContent
      : '';
}

function choosePlayerSearch(binding) {
  const select = document.getElementById(binding.selectId);
  const input = document.getElementById(binding.inputId);
  const query = normalizePlayerSearch(input.value);
  const options = availableOptions(binding);

  if (!query) {
    select.value = '';
    input.value = '';

    if (binding.comparison) {
      select.dispatchEvent(new Event('change'));
    }

    return false;
  }

  const match =
    options.find(option =>
      normalizePlayerSearch(option.textContent) === query
    ) ||
    options.find(option =>
      normalizePlayerSearch(option.textContent).startsWith(query)
    ) ||
    options.find(option =>
      normalizePlayerSearch(option.textContent).includes(query)
    );

  if (!match) {
    return false;
  }

  select.value = match.value;
  input.value = match.textContent;

  if (binding.comparison) {
    select.dispatchEvent(new Event('change'));
  }

  return true;
}

for (const binding of searchBindings) {
  const select = document.getElementById(binding.selectId);
  const input = document.getElementById(binding.inputId);

  new MutationObserver(() => {
    refreshPlayerSearch(binding);
  }).observe(select, {
    childList: true,
    subtree: true
  });

  input.addEventListener('input', () => {
    select.value = '';

    if (binding.comparison && !input.value.trim()) {
      select.dispatchEvent(new Event('change'));
    }
  });

  input.addEventListener('change', () => {
    choosePlayerSearch(binding);
  });

  input.addEventListener('keydown', event => {
    if (event.key !== 'Enter') {
      return;
    }

    const selected = choosePlayerSearch(binding);

    if (binding.comparison && selected) {
      event.preventDefault();
    }
  });

  refreshPlayerSearch(binding);
}

document.addEventListener('click', event => {
  if (!event.target.closest('[data-player]')) {
    return;
  }

  setTimeout(() => {
    refreshPlayerSearch(searchBindings[0]);
  });
});

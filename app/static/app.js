const $ = (id) => document.getElementById(id);

const state = {
  catalog: null,
  result: null
};

async function request(url) {
  const response = await fetch(url);
  let body = {};

  try {
    body = await response.json();
  } catch {
    body = {};
  }

  return {
    ok: response.ok,
    status: response.status,
    body
  };
}

async function json(url) {
  const response = await request(url);

  if (!response.ok) {
    throw new Error(
      response.body.detail || `Request failed (${response.status})`
    );
  }

  return response.body;
}

function loadMetricOptions() {
  const groups = {};

  for (const metric of state.catalog.metrics) {
    if (!groups[metric.category]) {
      groups[metric.category] = [];
    }

    groups[metric.category].push(metric);
  }

  $('metric').innerHTML = Object.entries(groups)
    .map(([category, metrics]) => {
      const options = metrics
        .map(metric => `<option value="${metric.id}">${metric.label}</option>`)
        .join('');

      return `<optgroup label="${category}">${options}</optgroup>`;
    })
    .join('');

  $('metric').value = 'pts';
}

function loadScopeOptions() {
  $('scope').innerHTML = Object.entries(state.catalog.scopes)
    .map(([id, label]) => `<option value="${id}">${label}</option>`)
    .join('');

  $('scope').value = 'window';
}

function updateCalculations() {
  const metric = state.catalog.metrics.find(
    item => item.id === $('metric').value
  );

  const current = $('calculation').value;

  $('calculation').innerHTML = metric.calculations
    .map(id => {
      const label = state.catalog.calculations[id];
      return `<option value="${id}">${label}</option>`;
    })
    .join('');

  $('calculation').value = metric.calculations.includes(current)
    ? current
    : metric.default_calculation;
}

function updateWindow() {
  $('window').disabled = $('scope').value !== 'window';
}

function resetToPoints() {
  $('metric').value = 'pts';
  updateCalculations();
  $('calculation').value = 'per_game';
}

async function loadMeta() {
  const [meta, catalog] = await Promise.all([
    json('/api/meta'),
    json('/api/metrics')
  ]);

  state.catalog = catalog;

  $('season').innerHTML = meta.seasons
    .map(season => `<option>${season}</option>`)
    .join('');

  $('updated').textContent = meta.built_at
    ? `Built ${new Date(meta.built_at).toLocaleString()}`
    : 'Database ready';

  loadMetricOptions();
  loadScopeOptions();
  updateCalculations();
  updateWindow();

  await loadPlayers();
}

async function loadPlayers(preferred) {
  const season = encodeURIComponent($('season').value);
  const players = await json(`/api/players?season=${season}`);

  $('player').innerHTML = players
    .map(player => `<option value="${player.id}">${player.name}</option>`)
    .join('');

  if (
    preferred &&
    players.some(player => String(player.id) === String(preferred))
  ) {
    $('player').value = preferred;
  }

  await runQuery();
}

function params(extra = {}) {
  return new URLSearchParams({
    season: $('season').value,
    player_id: $('player').value,
    metric: $('metric').value,
    calculation: $('calculation').value,
    scope: $('scope').value,
    window: $('window').value,
    ...extra
  });
}

async function runQuery(event, allowFallback = true) {
  event?.preventDefault();
  $('error').textContent = '';

  if (!$('player').value) {
    return;
  }

  try {
    const [resultResponse, similarResponse] = await Promise.all([
      request(`/api/result?${params()}`),
      request(`/api/similar?${params({ limit: 20 })}`)
    ]);

    if (!similarResponse.ok) {
      throw new Error(
        similarResponse.body.detail ||
        `Leaderboard request failed (${similarResponse.status})`
      );
    }

    const similar = similarResponse.body;
    const noSeasonResults =
      !similar.results ||
      similar.results.length === 0;

    if (
      allowFallback &&
      $('metric').value !== 'pts' &&
      noSeasonResults
    ) {
      resetToPoints();
      await runQuery(undefined, false);
      return;
    }

    if (!resultResponse.ok) {
      throw new Error(
        resultResponse.body.detail ||
        `Result request failed (${resultResponse.status})`
      );
    }

    const result = resultResponse.body;

    state.result = result;

    renderResult(result);
    renderSimilar(similar);
  } catch (error) {
    $('error').textContent = error.message;
  }
}

function renderResult(result) {
  const calculation = state.catalog.calculations[result.calculation];

  $('result-label').textContent = result.scope === 'window'
    ? `BEST ${result.window}-GAME ${result.metric_label.toUpperCase()} WINDOW`
    : `FULL-SEASON ${result.metric_label.toUpperCase()}`;

  $('result-name').textContent = result.player_name;

  $('result-season').textContent =
    `${result.season} regular season · ${calculation.toLowerCase()}`;

  $('result-value').innerHTML =
    `${Number(result.value).toFixed(1)} <span>${result.unit}</span>`;

  $('window-date').textContent = result.scope === 'window'
    ? `${result.start_date} to ${result.end_date}`
    : `${result.games_count} games`;

  const values = result.games
    .map(game => Number(game.chart_value))
    .filter(Number.isFinite);

  const minimum = Math.min(0, ...values);
  const maximum = Math.max(0, ...values);
  const range = maximum - minimum || 1;

  $('chart').innerHTML = result.games
    .map(game => {
      const value = Number(game.chart_value);
      const available = Number.isFinite(value);
      const height = available
        ? Math.max(2, ((value - minimum) / range) * 100)
        : 2;

      const displayed = available
        ? value.toFixed(2)
        : 'Unavailable';

      const selected = game.selected ? ' selected' : '';

      return `
        <button
          class="bar${selected}"
          title="${game.date} vs. ${game.opponent}: ${displayed} ${result.unit}"
          style="height:${height}%"
        >
          <span>${displayed}</span>
        </button>
      `;
    })
    .join('');
}

function renderSimilar(data) {
  $('results').innerHTML = data.results
    .map(row => `
      <button class="row" data-player="${row.player_id}">
        <span>${row.rank}</span>
        <b>${row.player_name}</b>
        <span>${Number(row.value).toFixed(1)} ${data.unit}</span>
        <span>${row.end_date}</span>
      </button>
    `)
    .join('');

  document.querySelectorAll('[data-player]').forEach(row => {
    row.addEventListener('click', async () => {
      $('player').value = row.dataset.player;
      await runQuery();
      window.scrollTo({ top: 150, behavior: 'smooth' });
    });
  });
}

$('controls').addEventListener('submit', runQuery);

$('season').addEventListener('change', () => {
  loadPlayers().catch(error => {
    $('error').textContent = error.message;
  });
});

$('metric').addEventListener('change', () => {
  updateCalculations();
});

$('scope').addEventListener('change', () => {
  updateWindow();
});

loadMeta().catch(error => {
  $('error').textContent = error.message;
});

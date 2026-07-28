const $ = (id) => document.getElementById(id);

const state = {
  catalog: null,
  result: null,
  comparisonActive: false,
  comparisonSeasonCustom: false
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

function loadComparisonPlayers(players) {
  const options = players
    .map(player => {
      let years = '';

      if (player.from_year && player.to_year) {
        years = ` (${player.from_year}–${player.to_year})`;
      } else if (player.from_year) {
        years = ` (${player.from_year})`;
      }

      return `<option value="${player.id}">${player.name}${years}</option>`;
    })
    .join('');

  $('compare').innerHTML =
    '<option value="">No comparison</option>' + options;
}

function loadSeasonOptions(seasons) {
  const options = seasons
    .map(season => `<option value="${season}">${season}</option>`)
    .join('');

  $('season').innerHTML = options;
  $('compare-season').innerHTML = options;
  $('compare-season').value = $('season').value;
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

function updateComparisonControls() {
  const active = Boolean($('compare').value);

  if (active && !state.comparisonActive) {
    $('compare-season').value = $('season').value;
    state.comparisonSeasonCustom = false;
  }

  $('compare-season-label').classList.toggle('hidden', !active);
  $('compare-season').disabled = !active;

  if (!active) {
    $('comparison-result').textContent = '';
    state.comparisonSeasonCustom = false;
  }

  state.comparisonActive = active;
}

function resetToPoints() {
  $('metric').value = 'pts';
  updateCalculations();
  $('calculation').value = 'per_game';
}

async function loadMeta() {
  const [meta, catalog, comparisonPlayers] = await Promise.all([
    json('/api/meta'),
    json('/api/metrics'),
    json('/api/all-players')
  ]);

  state.catalog = catalog;

  loadSeasonOptions(meta.seasons);
  loadMetricOptions();
  loadComparisonPlayers(comparisonPlayers);
  loadScopeOptions();
  updateCalculations();
  updateWindow();
  updateComparisonControls();

  $('updated').textContent = meta.built_at
    ? `Built ${new Date(meta.built_at).toLocaleString()}`
    : 'Database ready';

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

function comparisonParams() {
  const comparisonPlayer = $('compare').value;

  return new URLSearchParams({
    season: $('compare-season').value,
    primary_player_id: comparisonPlayer,
    comparison_player_id: comparisonPlayer,
    metric: $('metric').value,
    calculation: $('calculation').value,
    scope: $('scope').value,
    window: $('window').value
  });
}

async function runQuery(event, allowFallback = true) {
  event?.preventDefault();
  $('error').textContent = '';

  if (!$('player').value) {
    return;
  }

  try {
    const requests = [
      request(`/api/result?${params()}`),
      request(`/api/similar?${params({ limit: 20 })}`)
    ];

    if ($('compare').value) {
      requests.push(
        request(`/api/compare?${comparisonParams()}`)
      );
    }

    const responses = await Promise.all(requests);
    const resultResponse = responses[0];
    const similarResponse = responses[1];
    const comparisonResponse = responses[2];

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

    if (comparisonResponse && !comparisonResponse.ok) {
      throw new Error(
        comparisonResponse.body.detail ||
        `Comparison request failed (${comparisonResponse.status})`
      );
    }

    const result = resultResponse.body;

    state.result = result;

    renderResult(result);
    renderComparison(
      comparisonResponse ? comparisonResponse.body : null
    );
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

function renderComparison(data) {
  if (!data) {
    $('comparison-result').textContent = '';
    return;
  }

  const player = data.primary;
  const season = data.season;
  const prefix = `vs. ${player.player_name} (${season}): `;

  if (player.status === 'did_not_play') {
    if (player.value !== null) {
      $('comparison-result').textContent =
        `${prefix}${Number(player.value).toFixed(1)} ${data.unit} · did not play`;
    } else {
      $('comparison-result').textContent =
        `${prefix}unavailable · did not play`;
    }

    return;
  }

  if (player.status === 'no_qualifying_result') {
    $('comparison-result').textContent =
      `${prefix}no qualifying result`;

    return;
  }

  $('comparison-result').textContent =
    `${prefix}${Number(player.value).toFixed(1)} ${data.unit}`;
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
  if ($('compare').value && !state.comparisonSeasonCustom) {
    $('compare-season').value = $('season').value;
  }

  loadPlayers().catch(error => {
    $('error').textContent = error.message;
  });
});

$('compare').addEventListener('change', () => {
  updateComparisonControls();

  runQuery().catch(error => {
    $('error').textContent = error.message;
  });
});

$('compare-season').addEventListener('change', () => {
  state.comparisonSeasonCustom = true;

  runQuery().catch(error => {
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

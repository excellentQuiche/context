const $ = (id) => document.getElementById(id);

const state = {
  catalog: null,
  result: null,
  comparison: null,
  comparisonActive: false,
  comparisonSeasonCustom: false,
  imageCache: new Map()
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

function formatNumber(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return '—';
  }

  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2
  }).format(Number(value));
}

function formatDate(value) {
  if (!value) {
    return '—';
  }

  const [year, month, day] = value.split('-');

  if (!year || !month || !day) {
    return value;
  }

  return `${month}/${day}/${year}`;
}

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0])
    .join('')
    .toUpperCase();
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

function selectedMetric() {
  return state.catalog.metrics.find(
    item => item.id === $('metric').value
  );
}

function updateCalculations() {
  const metric = selectedMetric();
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
    state.comparison = null;
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
  return new URLSearchParams({
    primary_season: $('season').value,
    primary_player_id: $('player').value,
    comparison_season: $('compare-season').value,
    comparison_player_id: $('compare').value,
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
      requests.push(request(`/api/compare?${comparisonParams()}`));
    }

    const responses = await Promise.all(requests);
    const resultResponse = responses[0];
    const leadersResponse = responses[1];
    const comparisonResponse = responses[2];

    if (!leadersResponse.ok) {
      throw new Error(
        leadersResponse.body.detail ||
        `Leaderboard request failed (${leadersResponse.status})`
      );
    }

    const leaders = leadersResponse.body;
    const noSeasonResults = !leaders.results || leaders.results.length === 0;

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

    state.result = resultResponse.body;
    state.comparison = comparisonResponse ? comparisonResponse.body : null;

    renderResult(state.result, state.comparison);
    renderLeaders(leaders);
  } catch (error) {
    $('error').textContent = error.message;
  }
}

function resultDetail(player, scope, window) {
  if (player.status === 'did_not_play') {
    return 'Did not play';
  }

  if (player.status === 'no_qualifying_result') {
    return 'No qualifying result';
  }

  if (scope === 'window') {
    return `${window}-game streak`;
  }

  return `${player.games_count} games`;
}

function renderPlayerCard(prefix, player, unit, scope, window) {
  const seasonElement = prefix === 'comparison'
    ? $('comparison-season-text')
    : $('primary-season');

  $(`${prefix}-name`).textContent = player.player_name;
  seasonElement.textContent = player.season;
  $(`${prefix}-value`).textContent =
    player.value === null
      ? 'Unavailable'
      : `${formatNumber(player.value)} ${unit}`;
  $(`${prefix}-detail`).textContent = resultDetail(
    player,
    scope,
    window
  );

  loadPlayerMedia(
    `${prefix}-media`,
    player.player_id,
    player.season,
    player.player_name,
    player.team_name
  );
}

function renderResult(result, comparison) {
  const calculation = state.catalog.calculations[result.calculation];
  const metricLabel = result.metric_label;
  const primary = {
    player_id: result.player_id,
    player_name: result.player_name,
    team_name: result.team_name,
    season: result.season,
    status: 'played',
    value: result.value,
    games_count: result.games_count
  };

  $('result-label').textContent = result.scope === 'window'
    ? `BEST ${result.window}-GAME ${metricLabel.toUpperCase()} STREAK`
    : `FULL-SEASON ${metricLabel.toUpperCase()} · ${calculation.toUpperCase()}`;

  renderPlayerCard(
    'primary',
    primary,
    result.unit,
    result.scope,
    result.window
  );

  const comparing = Boolean(comparison);
  $('scoreboard').classList.toggle('single', !comparing);
  $('scoreboard').classList.toggle('comparison', comparing);
  $('score-divider').classList.toggle('hidden', !comparing);
  $('comparison-card').classList.toggle('hidden', !comparing);

  if (comparing) {
    renderPlayerCard(
      'comparison',
      comparison.comparison,
      comparison.unit,
      comparison.scope,
      comparison.window
    );
  } else {
    $('comparison-media').innerHTML = '';
  }

  $('window-date').textContent = result.scope === 'window'
    ? `${formatDate(result.start_date)}–${formatDate(result.end_date)}`
    : `${result.games_count} games`;

  $('chart-title').textContent = `Game-by-game ${metricLabel}`;
  $('leaders-title').textContent = `${result.season} leaders`;
  $('leaders-instruction').textContent =
    `Click a player to see their ${metricLabel}`;

  renderChart(result);
  updateImageCredits();
}

function renderChart(result) {
  const numericGames = result.games.filter(
    game => Number.isFinite(Number(game.chart_value))
  );
  const values = numericGames.map(game => Number(game.chart_value));
  const low = Math.min(0, ...values);
  const high = Math.max(0, ...values);
  const range = high - low || 1;
  const baseline = ((0 - low) / range) * 100;

  $('chart').style.setProperty('--baseline', `${baseline}%`);
  $('chart').innerHTML = result.games
    .map(game => {
      const value = Number(game.chart_value);
      const available = Number.isFinite(value);
      const selected = game.selected ? ' selected' : '';
      let bottom = baseline;
      let height = 1;

      if (available && value >= 0) {
        bottom = baseline;
        height = Math.max(1.5, (value / range) * 100);
      } else if (available) {
        bottom = ((value - low) / range) * 100;
        height = Math.max(1.5, (-value / range) * 100);
      }

      const title = available
        ? `${formatDate(game.date)} vs. ${game.opponent}: ${formatNumber(value)} ${result.unit}`
        : `${formatDate(game.date)} vs. ${game.opponent}: unavailable`;

      return `
        <div class="bar-slot" title="${title}">
          <div
            class="bar-fill${selected}"
            style="bottom:${bottom}%;height:${height}%"
          ></div>
        </div>
      `;
    })
    .join('');
}

function renderLeaders(data) {
  $('results').innerHTML = data.results
    .map(row => `
      <button class="row" data-player="${row.player_id}">
        <span>${row.rank}</span>
        <b>${row.player_name}</b>
        <span>${formatNumber(row.value)} ${data.unit}</span>
        <span>${formatDate(row.end_date)}</span>
      </button>
    `)
    .join('');

  document.querySelectorAll('[data-player]').forEach(row => {
    row.addEventListener('click', async () => {
      $('player').value = row.dataset.player;
      await runQuery();
      window.scrollTo({ top: 120, behavior: 'smooth' });
    });
  });
}

async function imageData(playerId, season) {
  const key = `${playerId}:${season}`;

  if (!state.imageCache.has(key)) {
    state.imageCache.set(
      key,
      json(
        `/api/player-image?player_id=${encodeURIComponent(playerId)}` +
        `&season=${encodeURIComponent(season)}`
      ).catch(() => ({ image: null }))
    );
  }

  return state.imageCache.get(key);
}

async function loadPlayerMedia(
  elementId,
  playerId,
  season,
  playerName,
  teamName
) {
  const element = $(elementId);
  const fallback = teamName || 'NBA';

  element.dataset.credit = '';
  element.innerHTML = `
    <div class="player-fallback">
      <strong>${initials(playerName)}</strong>
      <small>${fallback}</small>
    </div>
  `;

  const data = await imageData(playerId, season);

  if (!data.image || !data.image.url) {
    updateImageCredits();
    return;
  }

  element.dataset.credit =
    `${data.image.credit} · ${data.image.license} · ${data.image.source_url}`;

  element.innerHTML = `
    <img src="${data.image.url}" alt="${playerName}">
  `;

  updateImageCredits();
}

function updateImageCredits() {
  const credits = ['primary-media', 'comparison-media']
    .map(id => $(id).dataset.credit)
    .filter(Boolean);

  const unique = [...new Set(credits)];

  $('image-credits').innerHTML = unique
    .map(credit => {
      const parts = credit.split(' · ');
      const source = parts.pop();
      const label = parts.join(' · ');
      return `<a href="${source}" target="_blank" rel="noreferrer">Photo: ${label}</a>`;
    })
    .join(' · ');
}

function exportPdf() {
  if (!state.result) {
    return;
  }

  const previousTitle = document.title;
  const comparisonName = state.comparison
    ? ` vs ${state.comparison.comparison.player_name}`
    : '';

  document.title =
    `NBAContext - ${state.result.player_name}${comparisonName} - ` +
    `${state.result.metric_label}`;

  window.print();

  window.setTimeout(() => {
    document.title = previousTitle;
  }, 500);
}

$('controls').addEventListener('submit', runQuery);
$('export').addEventListener('click', exportPdf);

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

$('metric').addEventListener('change', updateCalculations);
$('scope').addEventListener('change', updateWindow);

loadMeta().catch(error => {
  $('error').textContent = error.message;
});

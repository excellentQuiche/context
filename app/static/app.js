const $ = (id) => document.getElementById(id);
const state = { result: null };

async function json(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error((await response.json()).detail || response.statusText);
  return response.json();
}

async function loadMeta() {
  const meta = await json('/api/meta');
  $('season').innerHTML = meta.seasons.map(s => `<option>${s}</option>`).join('');
  $('updated').textContent = `Built ${new Date(meta.built_at).toLocaleString()}`;
  await loadPlayers();
}

async function loadPlayers(preferred) {
  const players = await json(`/api/players?season=${encodeURIComponent($('season').value)}`);
  $('player').innerHTML = players.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
  if (preferred && players.some(p => String(p.id) === String(preferred))) $('player').value = preferred;
  await runQuery();
}

function params(extra = {}) {
  return new URLSearchParams({ season: $('season').value, player_id: $('player').value,
    metric: $('metric').value, window: $('window').value, ...extra });
}

async function runQuery(event) {
  event?.preventDefault();
  $('error').textContent = '';
  try {
    const [result, similar] = await Promise.all([
      json(`/api/result?${params()}`),
      json(`/api/similar?${params({ limit: 20 })}`)
    ]);
    state.result = result;
    renderResult(result);
    renderSimilar(similar);
  } catch (error) { $('error').textContent = error.message; }
}

function renderResult(result) {
  $('result-label').textContent = `BEST ${result.window}-GAME ${$('metric').selectedOptions[0].text.toUpperCase()} WINDOW`;
  $('result-name').textContent = result.player_name;
  $('result-season').textContent = `${result.season} regular season`;
  $('result-value').innerHTML = `${result.value.toFixed(1)} <span>${result.unit}</span>`;
  $('window-date').textContent = `Ends ${result.end_date}`;
  const key = $('metric').value === 'rebounds' ? 'reb' : $('metric').value === 'assists' ? 'ast' : 'pts';
  const max = Math.max(...result.games.map(g => Number(g[key]) || 0), 1);
  $('chart').innerHTML = result.games.map(g => `<button class="bar${g.selected ? ' selected' : ''}" title="${g.date}: ${g[key]}" style="height:${Math.max(2,(Number(g[key])||0)/max*100)}%"><span>${g[key] ?? 0}</span></button>`).join('');
}

function renderSimilar(data) {
  $('results').innerHTML = data.results.map(row => `<button class="row" data-player="${row.player_id}"><span>${row.rank}</span><b>${row.player_name}</b><span>${row.value.toFixed(1)} ${data.unit}</span><span>${row.end_date}</span></button>`).join('');
  document.querySelectorAll('[data-player]').forEach(row => row.addEventListener('click', async () => {
    $('player').value = row.dataset.player;
    await runQuery();
    window.scrollTo({ top: 150, behavior: 'smooth' });
  }));
}

$('controls').addEventListener('submit', runQuery);
$('season').addEventListener('change', () => loadPlayers());
loadMeta().catch(error => $('error').textContent = error.message);

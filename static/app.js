const roster = document.querySelector('#roster');
const playerCount = document.querySelector('#player-count');
const slotCount = document.querySelector('#slot-count');
const teamSize = document.querySelector('#team-size');
let chosenAlgorithm = 'hill_climbing';
const errorBox = document.querySelector('#error');

function buildRoster() {
  const count = Math.max(2, Math.min(32, Number(playerCount.value) || 8));
  const slots = Math.max(1, Math.min(12, Number(slotCount.value) || 1));
  playerCount.value = count;
  slotCount.value = slots;
  document.querySelector('[data-algorithm="brute_force"]').disabled = count > 8;
  if (count > 8 && chosenAlgorithm === 'brute_force') chooseAlgorithm('hill_climbing');
  roster.replaceChildren();
  for (let i = 0; i < count; i += 1) {
    const row = document.createElement('div');
    row.className = 'player-row';
    const name = document.createElement('input');
    name.type = 'text'; name.value = `Player ${i + 1}`; name.maxLength = 40;
    name.setAttribute('aria-label', `Player ${i + 1} name`);
    const rating = document.createElement('input');
    rating.type = 'number'; rating.min = 1; rating.max = 10; rating.value = (i * 3 + 5) % 10 + 1;
    rating.setAttribute('aria-label', `Player ${i + 1} rating`);
    const checks = document.createElement('div'); checks.className = 'slot-checks';
    checks.setAttribute('aria-label', `Player ${i + 1} availability`);
    for (let slot = 0; slot < slots; slot += 1) {
      const label = document.createElement('label'); label.className = 'slot-check';
      const input = document.createElement('input'); input.type = 'checkbox'; input.value = slot;
      input.checked = (i + slot) % 4 !== 0 || slot === i % slots;
      input.setAttribute('aria-label', `Available at slot ${slot}`);
      const caption = document.createElement('span'); caption.textContent = slot;
      label.append(input, caption); checks.append(label);
    }
    row.append(name, rating, checks); roster.append(row);
  }
}

function readPlayers() {
  return [...roster.children].map((row) => ({
    name: row.children[0].value.trim(),
    rating: row.children[1].value,
    free_slots: [...row.querySelectorAll('input[type="checkbox"]:checked')].map((box) => Number(box.value)),
  }));
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderResults(data) {
  document.querySelector('#empty-state').hidden = true;
  const results = document.querySelector('#results'); results.hidden = false;
  document.querySelector('#result-title').textContent = data.algorithm_name;
  document.querySelector('#total-cost').textContent = data.cost;
  document.querySelector('#run-time').textContent = `Computed in ${data.seconds.toFixed(4)} seconds · unavailable-player penalty ${data.penalty}`;
  const comparison = document.querySelector('#comparison'); comparison.replaceChildren();
  data.comparison.forEach((item) => {
    const card = element('div', 'compare-item');
    card.append(element('span', '', item.name), element('strong', '', item.cost)); comparison.append(card);
  });
  const matches = document.querySelector('#matches'); matches.replaceChildren();
  data.matches.forEach((match) => {
    const card = element('article', 'match-card');
    const top = element('div', 'match-top');
    top.append(element('span', '', `Match ${match.number} · Slot ${match.slot}`), element('span', '', `Imbalance ${match.imbalance}`));
    const teams = element('div', 'teams');
    for (const [label, players, total] of [['Team A', match.team_a, match.sum_a], ['Team B', match.team_b, match.sum_b]]) {
      const team = element('div', 'team');
      const heading = element('div', 'team-title'); heading.append(element('span', '', label), element('span', '', `Total ${total}`)); team.append(heading);
      players.forEach((player) => {
        const chip = element('div', 'player-chip');
        chip.append(element('b', '', player.name), element('span', 'rating-pill', `Rating ${player.rating}`)); team.append(chip);
      });
      teams.append(team);
    }
    card.append(top, teams);
    if (match.unavailable.length) card.append(element('div', 'warning', `⚠ Unavailable for slot ${match.slot}: ${match.unavailable.join(', ')}`));
    matches.append(card);
  });
}

document.querySelector('#build-roster').addEventListener('click', buildRoster);
document.querySelector('#run').addEventListener('click', async (event) => {
  errorBox.hidden = true;
  const button = event.currentTarget; button.disabled = true; button.querySelector('span').textContent = 'Searching…';
  try {
    const response = await fetch('/api/match', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({players: readPlayers(), team_size: Number(teamSize.value), slots: Number(slotCount.value),
        seed: Number(document.querySelector('#seed').value), algorithm: chosenAlgorithm}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The match could not be calculated.');
    renderResults(data);
  } catch (error) {
    errorBox.textContent = error.message || 'Could not connect to the match service.';
    errorBox.hidden = false;
  } finally {
    button.disabled = false; button.querySelector('span').textContent = 'Find fair teams';
  }
});

function chooseAlgorithm(name) {
  chosenAlgorithm = name;
  document.querySelectorAll('.method-button').forEach((button) => {
    const active = button.dataset.algorithm === name;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
}
document.querySelectorAll('.method-button').forEach((button) => {
  button.addEventListener('click', () => chooseAlgorithm(button.dataset.algorithm));
});
playerCount.addEventListener('change', buildRoster);
slotCount.addEventListener('change', buildRoster);
buildRoster();

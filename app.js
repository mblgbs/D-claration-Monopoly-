const form = document.getElementById('declaration-form');
const typeSelect = document.getElementById('type');
const eventSelect = document.getElementById('evenement');
const rows = document.getElementById('rows');
const emptyState = document.getElementById('empty-state');
const exportBtn = document.getElementById('export-btn');
const resetBtn = document.getElementById('reset-btn');

let cardData;
const STORAGE_KEY = 'declaration_app_entries';
let entries = [];
const API_BASE_URL = window.location.protocol.startsWith('http')
  ? window.location.origin
  : 'http://127.0.0.1:8000';

const formatType = {
  chance: 'Chance',
  communaute: 'Caisse communauté',
  impot: 'Impôt',
};

async function loadData() {
  const res = await fetch('./declaration_monopoly_cards.json');
  cardData = await res.json();
  fillEventOptions(typeSelect.value);
}

function getEventsByType(type) {
  if (type === 'chance') return cardData.chance;
  if (type === 'communaute') return cardData.communaute;

  return Object.values(cardData.impots).map((item) => item.regle);
}

function fillEventOptions(type) {
  const options = getEventsByType(type);
  eventSelect.innerHTML = '';

  options.forEach((label) => {
    const option = document.createElement('option');
    option.value = label;
    option.textContent = label;
    eventSelect.appendChild(option);
  });

  autoFillAmount();
}

function autoFillAmount() {
  const amountInput = document.getElementById('montant');
  const text = eventSelect.value || '';
  const match = text.match(/(\d+)€/);
  if (match) {
    amountInput.value = Number.parseInt(match[1], 10);
    return;
  }

  if (typeSelect.value === 'impot' && cardData?.impots) {
    const selectedTax = Object.values(cardData.impots).find((item) => item.regle === text);

    if (selectedTax && Number.isFinite(selectedTax.montant_fixe)) {
      amountInput.value = selectedTax.montant_fixe;
      return;
    }
  }

  if (/5%\s+de\s+vos\s+revenus/i.test(text) && /DEPART/i.test(text)) {
    amountInput.value = 10;
  }
}

function saveEntries() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
}

function loadEntries() {
  try {
    const fromStorage = JSON.parse(localStorage.getItem(STORAGE_KEY));
    entries = Array.isArray(fromStorage) ? fromStorage : [];
  } catch {
    entries = [];
  }
  renderEntries();
}

function renderEntries() {
  rows.innerHTML = '';

  entries.forEach((entry) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${entry.date}</td>
      <td>${entry.joueur}</td>
      <td>${formatType[entry.type]}</td>
      <td>${entry.evenement}</td>
      <td>${entry.montant} €</td>
      <td>${entry.notes || '-'}</td>
    `;
    if (typeof entry.solde === 'number') {
      tr.title = `Opération banque: ${entry.operation || 'n/a'} | Solde actuel: ${entry.solde} M$`;
    }
    rows.appendChild(tr);
  });

  emptyState.style.display = entries.length ? 'none' : 'block';
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const data = new FormData(form);
  const entry = {
    date: new Date().toLocaleString('fr-FR'),
    joueur: data.get('joueur'),
    type: data.get('type'),
    evenement: data.get('evenement'),
    montant: Number(data.get('montant')),
    notes: data.get('notes')?.toString().trim(),
  };

  try {
    const response = await fetch(`${API_BASE_URL}/declarations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(entry),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || 'Erreur lors de l\'enregistrement.');
    }

    entries.unshift({
      ...entry,
      operation: payload.entry.operation,
      solde: payload.bankAccount.solde,
    });
    saveEntries();
    renderEntries();
    form.reset();
    fillEventOptions(typeSelect.value);
  } catch (error) {
    alert(error.message);
  }
});

typeSelect.addEventListener('change', () => fillEventOptions(typeSelect.value));
eventSelect.addEventListener('change', autoFillAmount);

exportBtn.addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(entries, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `declarations-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

resetBtn.addEventListener('click', () => {
  entries = [];
  saveEntries();
  renderEntries();
});

loadEntries();
loadData();

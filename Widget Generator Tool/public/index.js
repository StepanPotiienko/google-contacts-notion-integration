const markers = []; // Store markers globally
const icons = {
  address: '<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>',
  contact: '<svg class="popup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
};

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function buildPopupHTML(c) {
  let html = '<div class="popup-header">';
  html += '<div class="popup-name">' + escapeHtml(c.name) + '</div>';
  html += '</div>';

  html += '<div class="popup-body">';
  if (c.address) {
    html += '<div class="popup-row">' + icons.address + '<span class="popup-value">' + escapeHtml(c.address) + '</span></div>';
  }
  html += '<div class="popup-coords">📍 ' + (c.lat || 0).toFixed(5) + ', ' + (c.lng || 0).toFixed(5) + '</div>';
  html += '</div>';
  return html;
}

const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources: {
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '© OpenStreetMap contributors'
      }
    },
    layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
  },
  center: [30.5241361, 50.4500336],
  zoom: 5
});

// Ensure clients are loaded; inject clients_array.js if needed
function ensureClientsLoaded() {
  return new Promise(resolve => {
    if (window.clients && Array.isArray(window.clients)) return resolve(window.clients);
    const script = document.createElement('script');
    script.src = 'clients_array.js';
    script.onload = () => resolve(window.clients || []);
    script.onerror = () => resolve(window.clients || []);
    document.head.appendChild(script);
  });
}

map.on('load', () => {
  ensureClientsLoaded().then(clients => {
    if (!clients || clients.length === 0) return;
    const bounds = new maplibregl.LngLatBounds();
    clients.forEach(c => bounds.extend([c.lng, c.lat]));
    map.fitBounds(bounds, { padding: 50, maxZoom: 12 });

    clients.forEach(c => {
      const el = document.createElement('div');
      el.className = 'marker';
      el.style.backgroundColor = c.color || '#ef4444';

      const popup = new maplibregl.Popup({ offset: 15, maxWidth: '320px' })
        .setHTML(buildPopupHTML(c));

      const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([c.lng, c.lat])
        .setPopup(popup)
        .addTo(map);

      // record marker index on client for reliable linking from search results
      c._markerIndex = markers.length;
      markers.push({ marker, client: c });
    });
  });
});

searchInput.addEventListener('input', (e) => {
  const query = e.target.value;
  if (query.trim() === '') {
    searchResults.classList.remove('active');
    return;
  }

  ensureClientsLoaded().then(() => {
    const results = (window.clients && window.clients.length) ? searchClients(query) : [];
    displaySearchResults(results);
  });
});

function searchClients(q) {
  const source = window.clients || [];
  const ql = q.toLowerCase();
  return source.filter(c => {
    return (c.name && c.name.toLowerCase().includes(ql)) ||
      (c.address && c.address.toLowerCase().includes(ql)) ||
      (c.contact && c.contact.toLowerCase().includes(ql)) ||
      (c.phone && c.phone.toLowerCase().includes(ql)) ||
      (c.email && c.email.toLowerCase().includes(ql));
  }).slice(0, 12);
}

function displaySearchResults(results) {
  searchResults.innerHTML = '';
  if (!results || results.length === 0) { searchResults.classList.remove('active'); return; }
  results.forEach(r => {
    const div = document.createElement('div');
    div.className = 'search-result';
    div.dataset.index = (typeof r._markerIndex !== 'undefined') ? r._markerIndex : -1;
    div.innerHTML = '<div class="result-name">' + escapeHtml(r.name) + '</div>' +
      '<div class="result-address">' + escapeHtml(r.address || '') + '</div>';
    div.addEventListener('click', () => {
      const idx = Number(div.dataset.index);
      const entry = markers[idx];
      if (entry) {
        entry.marker.togglePopup();
        map.flyTo({ center: [entry.client.lng, entry.client.lat], zoom: 12 });
      }
      searchResults.classList.remove('active');
    });
    searchResults.appendChild(div);
  });
  searchResults.classList.add('active');
}

// Close search results when clicking outside
document.addEventListener('mousedown', (e) => {
  if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
    searchResults.classList.remove('active');
  }
});

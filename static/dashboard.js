async function cargarGrafico() {
  const filtro = window.FILTRO_PERIODO || {};
  const qs = new URLSearchParams();
  if (filtro.anio) qs.set('anio', filtro.anio);
  if (filtro.mes) qs.set('mes', filtro.mes);
  const res = await fetch('/api/registros' + (qs.toString() ? `?${qs}` : ''));
  const data = await res.json();
  const ordenado = [...data].sort((a, b) => a.fecha.localeCompare(b.fecha));

  const labels = ordenado.map(r => r.fecha);
  const costo = ordenado.map(r => r.costo_total);
  const combustible = ordenado.map(r => r.combustible_l);
  const avance = ordenado.map(r => r.avance_m);

  const ctx = document.getElementById('chartEvolucion');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Costo total ($)',
          data: costo,
          borderColor: '#2f6f4f',
          backgroundColor: 'rgba(47,111,79,0.08)',
          yAxisID: 'y',
          tension: 0.25,
          fill: true,
        },
        {
          label: 'Avance (m lineal)',
          data: avance,
          borderColor: '#8a6d3b',
          backgroundColor: 'rgba(138,109,59,0.06)',
          yAxisID: 'y1',
          tension: 0.25,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      scales: {
        y: { position: 'left', title: { display: true, text: '$' } },
        y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'm lineal' } },
      },
      plugins: { legend: { position: 'bottom' } },
    },
  });
}

document.addEventListener('DOMContentLoaded', cargarGrafico);

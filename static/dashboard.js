async function cargarGraficos() {
  const filtro = window.FILTRO_PERIODO || {};
  const qs = new URLSearchParams();
  if (filtro.anio) qs.set('anio', filtro.anio);
  if (filtro.mes) qs.set('mes', filtro.mes);
  if (filtro.poza) qs.set('poza', filtro.poza);
  const res = await fetch('/api/registros' + (qs.toString() ? `?${qs}` : ''));
  const data = await res.json();
  const ordenado = [...data].sort((a, b) => a.fecha.localeCompare(b.fecha));
  const labels = ordenado.map(r => r.fecha);

  const ctxMantencion = document.getElementById('chartMantencion');
  if (ctxMantencion) {
    const horasOperadas = ordenado.map(r => r.horas_operadas);
    const horasParaMantencion = ordenado.map(r => r.hrs_para_mantencion);
    const coloresDisponibilidad = ordenado.map(r =>
      r.estado_mant === 'Alerta' ? '#b3492c' : '#2f6f4f'
    );
    const umbralAviso = window.AVISO_ANTICIPADO || 0;
    const umbral = ordenado.map(() => umbralAviso);

    new Chart(ctxMantencion, {
      data: {
        labels,
        datasets: [
          {
            type: 'bar',
            label: 'Horas operadas (disponibilidad)',
            data: horasOperadas,
            backgroundColor: coloresDisponibilidad,
            yAxisID: 'y',
          },
          {
            type: 'line',
            label: 'Horas para próxima mantención',
            data: horasParaMantencion,
            borderColor: '#3b6f8a',
            backgroundColor: 'rgba(59,111,138,0.06)',
            yAxisID: 'y1',
            tension: 0.25,
          },
          {
            type: 'line',
            label: 'Umbral de aviso',
            data: umbral,
            borderColor: '#b3492c',
            borderDash: [6, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        scales: {
          y: { position: 'left', title: { display: true, text: 'h operadas' } },
          y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'h para mantención' } },
        },
        plugins: { legend: { position: 'bottom' } },
      },
    });
  }

  const ctxEvolucion = document.getElementById('chartEvolucion');
  if (ctxEvolucion) {
    const costo = ordenado.map(r => r.costo_total);
    const combustible = ordenado.map(r => r.combustible_l);
    const avance = ordenado.map(r => r.avance_m);

    new Chart(ctxEvolucion, {
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
          {
            label: 'Combustible (L)',
            data: combustible,
            borderColor: '#3b6f8a',
            backgroundColor: 'rgba(59,111,138,0.06)',
            yAxisID: 'y2',
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
          y2: { position: 'right', offset: true, grid: { drawOnChartArea: false }, title: { display: true, text: 'L' } },
        },
        plugins: { legend: { position: 'bottom' } },
      },
    });
  }
}

document.addEventListener('DOMContentLoaded', cargarGraficos);

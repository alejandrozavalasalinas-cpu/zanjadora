const COLOR_OK = '#2f6f4f';
const COLOR_ALERT = '#b3492c';
const COLOR_COSTO = '#b5760f';
const COLOR_AVANCE = '#2a6fdb';
const COLOR_COMBUSTIBLE = '#00968f';
const COLOR_MANTENCION = '#6a4fb3';

function lineOptions(axisLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: { legend: { display: false } },
    scales: {
      y: { title: { display: true, text: axisLabel }, grid: { color: '#eef0f3' } },
      x: { grid: { display: false } },
    },
  };
}

function lineDataset(label, data, color) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: color + '1a',
    borderWidth: 2,
    pointRadius: 3,
    pointBackgroundColor: color,
    pointBorderColor: '#fff',
    pointBorderWidth: 1.5,
    tension: 0.3,
    fill: true,
  };
}

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

  const ctxDisponibilidad = document.getElementById('chartDisponibilidad');
  if (ctxDisponibilidad) {
    const dispRes = await fetch('/api/disponibilidad' + (qs.toString() ? `?${qs}` : ''));
    const disp = await dispRes.json();
    const dias = disp.dias || [];
    const dispLabels = dias.map(d => d.fecha);
    const dispPct = dias.map(d => d.disponibilidad_pct);
    const dispColores = dias.map(d => d.hay_alerta ? COLOR_ALERT : COLOR_OK);
    const meta = dias.map(() => 100);

    const acumuladoEl = document.getElementById('dispAcumuladoMes');
    if (acumuladoEl) {
      acumuladoEl.textContent = disp.acumulado_pct != null
        ? disp.acumulado_pct.toFixed(1) + '%'
        : '—';
    }

    new Chart(ctxDisponibilidad, {
      data: {
        labels: dispLabels,
        datasets: [
          {
            type: 'bar',
            label: 'Disponibilidad (%)',
            data: dispPct,
            backgroundColor: dispColores,
            borderRadius: 4,
            maxBarThickness: 28,
          },
          {
            type: 'line',
            label: 'Jornada (100%)',
            data: meta,
            borderColor: '#c3c2b7',
            borderDash: [6, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: lineOptions('% de 9 h'),
    });
  }

  const ctxMantencion = document.getElementById('chartMantencion');
  if (ctxMantencion) {
    const horasParaMantencion = ordenado.map(r => r.hrs_para_mantencion);
    const umbral = ordenado.map(() => window.AVISO_ANTICIPADO || 0);

    const ultimaConDato = [...ordenado].reverse().find(r => r.hrs_para_mantencion != null);
    const horasRestantesEl = document.getElementById('mantHorasRestantes');
    if (horasRestantesEl) {
      if (ultimaConDato) {
        const horas = ultimaConDato.hrs_para_mantencion;
        horasRestantesEl.textContent = Math.round(horas).toLocaleString('es-CL') + ' h';
        horasRestantesEl.style.color = horas <= (window.AVISO_ANTICIPADO || 0) ? COLOR_ALERT : COLOR_OK;
      } else {
        horasRestantesEl.textContent = '—';
      }
    }
    new Chart(ctxMantencion, {
      type: 'line',
      data: {
        labels,
        datasets: [
          lineDataset('Horas para mantención', horasParaMantencion, COLOR_MANTENCION),
          {
            label: 'Umbral de aviso',
            data: umbral,
            borderColor: COLOR_ALERT,
            borderDash: [6, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: lineOptions('h restantes'),
    });
  }

  const ctxCosto = document.getElementById('chartCosto');
  if (ctxCosto) {
    const costo = ordenado.map(r => r.costo_total);
    new Chart(ctxCosto, {
      type: 'line',
      data: { labels, datasets: [lineDataset('Costo total', costo, COLOR_COSTO)] },
      options: lineOptions('$'),
    });
  }

  const ctxAvance = document.getElementById('chartAvance');
  if (ctxAvance) {
    const avance = ordenado.map(r => r.avance_m);
    new Chart(ctxAvance, {
      type: 'line',
      data: { labels, datasets: [lineDataset('Avance', avance, COLOR_AVANCE)] },
      options: lineOptions('m lineal'),
    });
  }

  const ctxCombustible = document.getElementById('chartCombustible');
  if (ctxCombustible) {
    const combustible = ordenado.map(r => r.combustible_l);
    new Chart(ctxCombustible, {
      type: 'line',
      data: { labels, datasets: [lineDataset('Combustible', combustible, COLOR_COMBUSTIBLE)] },
      options: lineOptions('L'),
    });
  }
}

document.addEventListener('DOMContentLoaded', cargarGraficos);

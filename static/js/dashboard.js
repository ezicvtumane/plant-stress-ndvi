/**
 * Plant Stress Web Station - Dashboard Interactions
 * Ковалева Алиса, Большие вызовы (Сириус)
 */

function adjTemp(id, delta) {
    let inp = document.getElementById(id);
    if (!inp) return;
    let cur = parseFloat(inp.value.replace(',', '.')) || 23.5;
    inp.value = (cur + delta).toFixed(1);
}

function toggleNoSoilSensor(checked) {
    let inp = document.getElementById('edit_soil');
    if (!inp) return;
    if (checked) {
        inp.value = '--';
        inp.readOnly = true;
        inp.style.background = '#f1f5f9';
        inp.style.color = '#64748b';
        inp.style.cursor = 'not-allowed';
    } else {
        if (inp.value === '--') inp.value = '';
        inp.readOnly = false;
        inp.style.background = '#ffffff';
        inp.style.color = '#000000';
        inp.style.cursor = 'text';
        inp.focus();
    }
}

function openEditModal(id, grp, ts, tLeaf, weight, soil) {
    let measIdInp = document.getElementById('edit_meas_id');
    let cohortInp = document.getElementById('edit_cohort');
    let tsInp = document.getElementById('edit_timestamp');
    let titleEl = document.getElementById('editModalTitle');
    let tLeafInp = document.getElementById('edit_t_leaf');
    let weightInp = document.getElementById('edit_weight');
    let soilInp = document.getElementById('edit_soil');
    let noSoilChk = document.getElementById('edit_no_soil_sensor');
    let modal = document.getElementById('editModal');

    if (!modal) return;

    if (measIdInp) measIdInp.value = id;
    if (cohortInp) cohortInp.value = grp || '';
    if (tsInp) tsInp.value = ts || '';
    if (titleEl) titleEl.innerText = '✏️ Коррекция замера #' + id + (grp ? ' (' + grp + ')' : '');

    let cleanT = (tLeaf || '').replace(' °C', '').replace('°C', '').trim();
    if (cleanT === '--' || cleanT.toLowerCase().indexOf('none') !== -1) {
        cleanT = (id === '73' && grp === 'Осмос') ? '30.2' : '23.5';
    }
    if (tLeafInp) tLeafInp.value = cleanT;

    let cleanW = (weight || '').replace(' г', '').replace('г', '').trim();
    if (cleanW === '--') cleanW = '';
    if (weightInp) weightInp.value = cleanW;

    let cleanS = (soil || '').replace('%', '').trim();
    let isNoSensor = (cleanS === '--' || cleanS.toLowerCase().indexOf('none') !== -1 || cleanS === '');

    if (noSoilChk) noSoilChk.checked = isNoSensor;
    if (soilInp) {
        if (isNoSensor) {
            soilInp.value = '--';
            soilInp.readOnly = true;
            soilInp.style.background = '#f1f5f9';
            soilInp.style.color = '#64748b';
            soilInp.style.cursor = 'not-allowed';
        } else {
            soilInp.value = cleanS;
            soilInp.readOnly = false;
            soilInp.style.background = '#ffffff';
            soilInp.style.color = '#000000';
            soilInp.style.cursor = 'text';
        }
    }

    modal.style.display = 'flex';
}

function closeEditModal() {
    let modal = document.getElementById('editModal');
    if (modal) modal.style.display = 'none';
}

function dismissBanner() {
    let el = document.getElementById('statusAlert');
    if (el) {
        el.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        el.style.opacity = '0';
        el.style.transform = 'translateY(-8px)';
        setTimeout(() => el.remove(), 400);
    }
    if (window.history && window.history.replaceState) {
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

function openNewExpModal() {
    let m = document.getElementById('newExpModal');
    if (m) m.style.display = 'flex';
}

function closeNewExpModal() {
    let m = document.getElementById('newExpModal');
    if (m) m.style.display = 'none';
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('statusAlert')) {
        if (window.history && window.history.replaceState) {
            window.history.replaceState({}, document.title, window.location.pathname);
        }
        setTimeout(function() {
            dismissBanner();
        }, 4500);
    }
});

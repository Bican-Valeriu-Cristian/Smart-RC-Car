// Trimite datele de control către server
function send(x, y, speed, angle) {
    fetch('/drive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y, speed, angle })
    }).catch(console.error);
}

// Limitează la ~6-8 comenzi/s
let lastDriveTs = 0;
const DRIVE_INTERVAL_MS = 150;

(function wrapSendIfExists() {
    if (typeof window.send === 'function') {
        const origSend = window.send;
        window.send = function (x, y, speed, angle) {
            const now = performance.now();
            if (now - lastDriveTs < DRIVE_INTERVAL_MS) return;
            lastDriveTs = now;
            try { origSend(x, y, speed, angle); } catch (e) { console.error(e); }
        };
    }
})();

// ================= DISTANȚĂ SENZOR =================
let distBusy = false;

function updateDistance() {
    if (distBusy) return;
    distBusy = true;

    fetch('/distance', { cache: 'no-store' })
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('distance');
            if (!el) return;
            if (typeof data.distance === 'number' && data.distance >= 0) {
                el.textContent = data.distance.toFixed(1);
            } else {
                el.textContent = '--';
            }
        })
        .catch(() => {
            const el = document.getElementById('distance');
            if (el) el.textContent = '--';
        })
        .finally(() => { distBusy = false; });
}

// 300–500 ms e un compromis bun; folosim 400 ms
setInterval(updateDistance, 400);
updateDistance();

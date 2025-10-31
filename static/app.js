// functie trimite date de control catre server
function send(x, y, speed, angle) {
    fetch('/drive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y, speed, angle })
    }).catch(console.error);
}

// limita la 10 cereri pe secunda
let lastDriveTs = 0;
const DRIVE_INTERVAL_MS = 100;

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

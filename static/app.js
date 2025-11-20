let lastDriveTs = 0;
const DRIVE_INTERVAL_MS = 70;

function send(x, y, speed, angle) {
    const now = performance.now();
    if (speed !== 0 && (now - lastDriveTs < DRIVE_INTERVAL_MS)) {
        return;
    }

    lastDriveTs = now;

    fetch('/drive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y, speed, angle })
    }).catch(error => {
        console.error("Eroare conexiune:", error);
    });
}
// Actualizare distanță la fiecare 250ms 
setInterval(() => {
    fetch('/distance')
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById("status");
            if (el) {
                if (data.cm === 0) {
                    el.innerText = "Distanta: --";
                } else {
                    el.innerText = "Distanta: " + data.cm + " cm";
                }
            }
        })
        .catch(e => console.log("Eroare senzor")); // Ignorăm erorile silențios
}, 250);
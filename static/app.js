// 1. LOGICA JOYSTICK
var canvas, ctx, width, height, radius, x_orig, y_orig;
let coord = { x: 0, y: 0 };
let paint = false;

document.addEventListener('DOMContentLoaded', () => {
    canvas = document.getElementById('canvas');
    if (canvas) {
        ctx = canvas.getContext('2d');

        document.addEventListener('mousedown', startDrawing);
        document.addEventListener('mouseup', stopDrawing);
        document.addEventListener('mousemove', Draw);

        document.addEventListener('touchstart', startDrawing, { passive: false });
        document.addEventListener('touchend', stopDrawing);
        document.addEventListener('touchcancel', stopDrawing);
        document.addEventListener('touchmove', Draw, { passive: false });

        //canvas.addEventListener('mouseleave', stopDrawing);
        window.addEventListener('blur', stopDrawing);

        setTimeout(resize, 100);
        window.addEventListener('resize', resize);
    }
    initChartsSafe();
});

// FUNCTIA RESIZE MODIFICATA PENTRU LAPTOP 
function resize() {
    const parent = document.querySelector('.joystick-box');
    if (parent) {
        width = parent.clientWidth - 10;
        radius = width / 12;

        if (radius < 35) radius = 35;
        if (radius > 70) radius = 70;

        // Înălțimea canvasului
        height = radius * 5.3;

        ctx.canvas.width = width;
        ctx.canvas.height = height;

        background();
        joystick(width / 2, height / 2);
    }
}

// Cerc exterior
function background() {
    x_orig = width / 2;
    y_orig = height / 2;
    ctx.beginPath();
    ctx.arc(x_orig, y_orig, radius + 10, 0, Math.PI * 2, true);
    ctx.fillStyle = '#ECE5E5';
    ctx.fill();
}

// Cerc interior (joystick)
function joystick(x, y) {
    ctx.beginPath();
    ctx.arc(x, y, radius * 0.4, 0, Math.PI * 2, true);
    ctx.fillStyle = '#F08080';
    ctx.fill();
    ctx.strokeStyle = '#F6ABAB';
    ctx.lineWidth = 4;
    ctx.stroke();
}
// Obține coordonatele mouse-ului sau ale atingerii
function getPosition(event) {
    if (!event) return;
    var mouse_x = event.clientX || (event.touches && event.touches[0] ? event.touches[0].clientX : undefined);
    var mouse_y = event.clientY || (event.touches && event.touches[0] ? event.touches[0].clientY : undefined);
    if (mouse_x !== undefined && mouse_y !== undefined) {
        var rect = canvas.getBoundingClientRect();
        coord.x = mouse_x - rect.left;
        coord.y = mouse_y - rect.top;
    }
}
// Verifică dacă coordonatele sunt în interiorul cercului exterior
function is_it_in_the_circle() {
    var current_radius = Math.sqrt(Math.pow(coord.x - x_orig, 2) + Math.pow(coord.y - y_orig, 2));
    return radius >= current_radius;
}
// Începe desenarea joystick-ului
function startDrawing(event) {
    if (event.target !== canvas) return;
    if (event.type === 'touchstart') event.preventDefault();
    paint = true;
    getPosition(event);
    if (is_it_in_the_circle()) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        background();
        joystick(coord.x, coord.y);
        Draw(event);
    }
}
// Oprește desenarea și resetează joystick-ul
function stopDrawing() {
    paint = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    background();
    joystick(width / 2, height / 2);
    updateUI(0, 0, 0);
    send(0, 0, 0, 0);
}
// Desenează joystick-ul în funcție de mișcarea mouse-ului sau a atingerii
function Draw(event) {
    if (paint) {
        if (event.type === 'touchmove') event.preventDefault();
        getPosition(event);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        background();

        var angle = Math.atan2((coord.y - y_orig), (coord.x - x_orig));
        var angle_in_degrees, x, y;

        if (Math.sign(angle) == -1) {
            angle_in_degrees = Math.round(-angle * 180 / Math.PI);
        } else {
            angle_in_degrees = Math.round(360 - angle * 180 / Math.PI);
        }

        if (is_it_in_the_circle()) {
            joystick(coord.x, coord.y);
            x = coord.x;
            y = coord.y;
        } else {
            x = radius * Math.cos(angle) + x_orig;
            y = radius * Math.sin(angle) + y_orig;
            joystick(x, y);
        }

        var raw_x = x - x_orig;
        var raw_y = y_orig - y;
        var x_percent = Math.round((raw_x / radius) * 100);
        var y_percent = Math.round((raw_y / radius) * 100);

        if (x_percent > 100) x_percent = 100;
        if (x_percent < -100) x_percent = -100;
        if (y_percent > 100) y_percent = 100;
        if (y_percent < -100) y_percent = -100;

        var speed = Math.round(Math.sqrt(Math.pow(x_percent, 2) + Math.pow(y_percent, 2)));
        if (speed > 60) speed = 60;

        updateUI(x_percent, y_percent, speed);
        send(x_percent, y_percent, speed, angle_in_degrees);
    }
}
// Actualizează valorile afișate în UI
function updateUI(x, y, s) {
    const elX = document.getElementById("x_coordinate");
    const elY = document.getElementById("y_coordinate");
    const elS = document.getElementById("speed");
    if (elX) elX.innerText = x;
    if (elY) elY.innerText = y;
    if (elS) elS.innerText = s;
}


// 2. CONFIGURARE DASHBOARD - GAUGE GAZ

var gasGauge = null;

function initChartsSafe() {
    try {
        if (typeof Gauge !== 'undefined') {
            var gaugeOpts = {
                angle: 0.0, lineWidth: 0.2, radiusScale: 0.9,
                pointer: { length: 0.45, strokeWidth: 0.035, color: '#ccc' },
                limitMax: false, limitMin: false,
                generateGradient: true, highDpiSupport: true,
                // Culorile desenate fizic de la Stânga la Dreapta
                staticZones: [
                    { strokeStyle: "#30B32D", min: 0, max: 50 },   // VERDE (Stânga)
                    { strokeStyle: "#FFDD00", min: 50, max: 75 },  // GALBEN (Mijloc)
                    { strokeStyle: "#F03E3E", min: 75, max: 100 }  // ROȘU (Dreapta)
                ],
            };
            var target = document.getElementById('gasGauge');
            if (target) {
                target.height = 90;
                gasGauge = new Gauge(target).setOptions(gaugeOpts);
                gasGauge.maxValue = 100;   // Limita dreaptă
                gasGauge.setMinValue(0);   // Limita stângă
                gasGauge.animationSpeed = 32;
                gasGauge.set(0); // La pornire, trimitem acul în stânga de tot (pe verde)
            }
        }
    } catch (e) {
        console.error("Eroare initializare grafice:", e);
    }
}
// 3. COMUNICARE SERVER 
setInterval(() => {
    fetch('/telemetry')
        .then(r => r.json())
        .then(data => {
            // A. HUD Distanță (Avertizare mică și discretă)
            const hudDist = document.getElementById("hud-distance");
            const hudAlert = document.getElementById("hud-alert"); // Îl vom ține ascuns mereu

            if (hudDist) {
                // Ascundem definitiv cutia uriașă de pe mijlocul ecranului
                if (hudAlert) hudAlert.style.display = "none";

                if (data.distance_cm > 2 && data.distance_cm < 20) {
                    // Face textul mic de jos roșu și îi adaugă simbolul de pericol
                    hudDist.style.color = "#ff0055"; // neon-red
                    hudDist.style.borderColor = "#ff0055";
                    hudDist.innerText = `DIST: ${data.distance_cm} cm ⚠️ PERICOL`;
                } else {
                    // Când e drum liber, revine la verde normal
                    hudDist.style.color = "#00ff00";
                    hudDist.style.borderColor = "#00ff00";
                    hudDist.innerText = `DIST: ${data.distance_cm} cm`;
                }
            }

            // B. Gauge Gaz (Calitate Aer)
            let voltaj = data.gas_volts;
            voltaj = Math.max(0, Math.min(5, voltaj)); // Limităm între 0V și 5V

            // 1. Calculăm unde stă acul (0V = stânga/0, 5V = dreapta/100)
            let pozitie_ac = Math.round((voltaj / 5) * 100);

            // Mutăm acul pe grafic (de la stânga spre dreapta)
            if (gasGauge) gasGauge.set(pozitie_ac);

            // 2. Calculăm procentul afișat (invers față de ac!)
            // Când acul e în stânga (0), calitatea e 100%. Când acul e în dreapta (100), calitatea e 0%.
            let calitate_aer = 100 - pozitie_ac;

            const gasVal = document.getElementById("gas-value");
            if (gasVal) gasVal.innerText = calitate_aer;

            // 3. Afișăm statusul
            const gasStatus = document.getElementById("gas-status");
            if (gasStatus) {
                if (voltaj <= 2.5) {
                    gasStatus.innerText = "🟢 AER CURAT";
                    gasStatus.style.color = "#30B32D"; // Verde
                }
                else if (voltaj <= 3.75) {
                    gasStatus.innerText = "🟡 AVERTIZARE FUM/GAZ";
                    gasStatus.style.color = "#FFDD00"; // Galben
                }
                else {
                    gasStatus.innerText = "🔴 PERICOL TOXICITATE";
                    gasStatus.style.color = "#F03E3E"; // Roșu
                }
            }

            // C. Afișare Temperatură + Umiditate
            const textTemp = document.getElementById("text-temp");
            const textHum = document.getElementById("text-hum");

            if (textTemp && data.temp > 0) {
                textTemp.innerText = `Temp: ${data.temp} °C`;
            }
            if (textHum && data.hum > 0) {
                textHum.innerText = `Umiditate: ${data.hum} %`;
            }

            // ------------------------------------------------------------------
            // D. SINCRONIZARE BUTON AUTO-PILOT (Se stinge când misiunea e gata)
            // ------------------------------------------------------------------
            // ATENȚIE: Înlocuiește 'btn-autopilot' cu ID-ul real al butonului tău din HTML!
            const autoButton = document.getElementById('btn-autopilot');

            if (autoButton) {
                // Folosim clasele din CSS-ul tău pentru a păstra efectele de neon și border!
                if (data.auto_mode === true) {
                    autoButton.classList.add("active-auto"); // Îi dă verdele #2ecc71 și umbra
                    autoButton.classList.remove("btn-oprit");
                } else {
                    autoButton.classList.remove("active-auto");
                    autoButton.classList.add("btn-oprit");   // Revine la gri-ul #444 și border #222
                }
            }
            // ------------------------------------------------------------------

        })
        .catch(e => {
            console.error("Eroare la preluarea telemetriei:", e);
        });
}, 1000);

// -- DRIVE LOGIC --
let lastDriveTs = 0;
const DRIVE_INTERVAL_MS = 100;
function send(x, y, speed, angle) {
    const now = performance.now();
    if (speed !== 0 && (now - lastDriveTs < DRIVE_INTERVAL_MS)) return;
    lastDriveTs = now;
    fetch('/drive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y, speed, angle })
    }).catch(e => console.error(e));
}
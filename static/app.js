// ==========================================
// 1. LOGICA JOYSTICK (DESIGN VECHI + COMPACT)
// ==========================================
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

        canvas.addEventListener('mouseleave', stopDrawing);
        window.addEventListener('blur', stopDrawing);

        setTimeout(resize, 100);
        window.addEventListener('resize', resize);
    }
    initChartsSafe();
});

// --- FUNCTIA RESIZE MODIFICATA PENTRU LAPTOP ---
function resize() {
    const parent = document.querySelector('.joystick-box');
    if (parent) {
        width = parent.clientWidth - 10;

        // --- MODIFICARE CRITICĂ PENTRU MĂRIME ---
        // Împărțim la 6 pentru un cerc micuț
        radius = width / 12;

        // Limite de siguranță (să nu fie nici prea mic, nici prea mare)
        if (radius < 35) radius = 35;
        if (radius > 70) radius = 70; // Maxim 70px rază

        // Înălțimea totală a canvasului redusă drastic
        height = radius * 5.3; // Era * 4 sau * 5

        ctx.canvas.width = width;
        ctx.canvas.height = height;

        background();
        joystick(width / 2, height / 2);
    }
}

// Design Vechi: Fundal
function background() {
    x_orig = width / 2;
    y_orig = height / 2;
    ctx.beginPath();
    ctx.arc(x_orig, y_orig, radius + 10, 0, Math.PI * 2, true);
    ctx.fillStyle = '#ECE5E5';
    ctx.fill();
}

// Design Vechi: Buton
function joystick(x, y) {
    ctx.beginPath();
    ctx.arc(x, y, radius * 0.4, 0, Math.PI * 2, true);
    ctx.fillStyle = '#F08080';
    ctx.fill();
    ctx.strokeStyle = '#F6ABAB';
    ctx.lineWidth = 4;
    ctx.stroke();
}

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

function is_it_in_the_circle() {
    var current_radius = Math.sqrt(Math.pow(coord.x - x_orig, 2) + Math.pow(coord.y - y_orig, 2));
    return radius >= current_radius;
}

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

function stopDrawing() {
    paint = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    background();
    joystick(width / 2, height / 2);
    updateUI(0, 0, 0);
    send(0, 0, 0, 0);
}

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
        var raw_y = y - y_orig;
        var x_percent = Math.round((raw_x / radius) * 100);
        var y_percent = Math.round((raw_y / radius) * 100);

        if (x_percent > 100) x_percent = 100;
        if (x_percent < -100) x_percent = -100;
        if (y_percent > 100) y_percent = 100;
        if (y_percent < -100) y_percent = -100;

        var speed = Math.round(Math.sqrt(Math.pow(x_percent, 2) + Math.pow(y_percent, 2)));
        if (speed > 100) speed = 100;

        updateUI(x_percent, y_percent, speed);
        send(x_percent, y_percent, speed, angle_in_degrees);
    }
}

function updateUI(x, y, s) {
    const elX = document.getElementById("x_coordinate");
    const elY = document.getElementById("y_coordinate");
    const elS = document.getElementById("speed");
    if (elX) elX.innerText = x;
    if (elY) elY.innerText = y;
    if (elS) elS.innerText = s;
}

// ==========================================
// 2. CONFIGURARE DASHBOARD (GRAFICE DUBLE)
// ==========================================
var gasGauge = null;
var tempChart = null;

function initChartsSafe() {
    try {
        // --- GAUGE GAZ ---
        if (typeof Gauge !== 'undefined') {
            var gaugeOpts = {
                angle: 0.0, lineWidth: 0.2, radiusScale: 0.9,
                pointer: { length: 0.45, strokeWidth: 0.035, color: '#ccc' },
                limitMax: false, limitMin: false,
                colorStart: '#6FADCF', colorStop: '#8FC0DA', strokeColor: '#222',
                generateGradient: true, highDpiSupport: true,
                staticZones: [
                    { strokeStyle: "#30B32D", min: 0, max: 1.5 },
                    { strokeStyle: "#FFDD00", min: 1.5, max: 2.5 },
                    { strokeStyle: "#F03E3E", min: 2.5, max: 5.0 }
                ],
            };
            var target = document.getElementById('gasGauge');
            if (target) {
                target.height = 90;
                gasGauge = new Gauge(target).setOptions(gaugeOpts);
                gasGauge.maxValue = 5.0;
                gasGauge.setMinValue(0);
                gasGauge.animationSpeed = 32;
                gasGauge.set(0);
            }
        }

        // --- CHART TEMPERATURA + UMIDITATE ---
        if (typeof Chart !== 'undefined') {
            var ctxElement = document.getElementById('tempChart');
            if (ctxElement) {
                var ctxChart = ctxElement.getContext('2d');

                // Gradient Verde (Temp)
                var gradTemp = ctxChart.createLinearGradient(0, 0, 0, 100);
                gradTemp.addColorStop(0, 'rgba(0, 255, 0, 0.4)');
                gradTemp.addColorStop(1, 'rgba(0, 255, 0, 0.0)');

                // Gradient Albastru (Umiditate)
                var gradHum = ctxChart.createLinearGradient(0, 0, 0, 100);
                gradHum.addColorStop(0, 'rgba(0, 255, 255, 0.2)');
                gradHum.addColorStop(1, 'rgba(0, 255, 255, 0.0)');

                tempChart = new Chart(ctxChart, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [
                            // DATASET 1: Temperatura (Stanga, Verde)
                            {
                                label: 'Temp (°C)',
                                data: [],
                                borderColor: '#00ff00',
                                backgroundColor: gradTemp,
                                borderWidth: 2,
                                tension: 0.4,
                                fill: true,
                                pointRadius: 0,
                                yAxisID: 'y', // Axa stanga
                            },
                            // DATASET 2: Umiditate (Dreapta, Albastru Cyan)
                            {
                                label: 'Umiditate (%)',
                                data: [],
                                borderColor: '#00ffff', // Cyan Neon
                                backgroundColor: gradHum,
                                borderWidth: 1, // Linie mai subtire
                                tension: 0.4,
                                fill: true,
                                pointRadius: 0,
                                yAxisID: 'y1', // Axa dreapta
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } }, // Ascundem legenda ca sa fie curat
                        scales: {
                            x: { display: false },
                            // AXA STANGA (Temp)
                            y: {
                                position: 'left',
                                grid: { color: 'rgba(255,255,255,0.1)' },
                                ticks: { color: '#00ff00', font: { size: 10 } } // Scris Verde
                            },
                            // AXA DREAPTA (Umiditate)
                            y1: {
                                position: 'right',
                                grid: { drawOnChartArea: false }, // Fara grilaj dublu
                                ticks: { color: '#00ffff', font: { size: 10 } }, // Scris Albastru
                                min: 0,
                                max: 100 // Umiditatea e mereu 0-100%
                            }
                        },
                        animation: false
                    }
                });
            }
        }
    } catch (e) {
        console.error("Eroare initializare grafice:", e);
    }
}

// ==========================================
// 3. COMUNICARE SERVER 
// ==========================================
setInterval(() => {
    fetch('/telemetry')
        .then(r => r.json())
        .then(data => {
            // A. HUD
            const hudDist = document.getElementById("hud-distance");
            const hudAlert = document.getElementById("hud-alert");
            if (hudDist) {
                if (data.distance_cm > 0 && data.distance_cm < 20) {
                    hudDist.style.color = "red";
                    hudDist.style.borderColor = "red";
                    if (hudAlert) hudAlert.style.display = "block";
                } else {
                    hudDist.style.color = "#00ff00";
                    hudDist.style.borderColor = "#00ff00";
                    if (hudAlert) hudAlert.style.display = "none";
                }
                hudDist.innerText = `DIST: ${data.distance_cm} cm`;
            }

            // B. Gauge Gaz
            if (gasGauge) gasGauge.set(data.gas_volts);
            const gasVal = document.getElementById("gas-value");
            if (gasVal) gasVal.innerText = data.gas_volts.toFixed(2);

            const gasStatus = document.getElementById("gas-status");
            if (gasStatus) {
                if (data.gas_alert) {
                    gasStatus.innerText = "⚠️ DETECȚIE GAZ!";
                    gasStatus.style.color = "red";
                } else {
                    gasStatus.innerText = "AER CURAT";
                    gasStatus.style.color = "#888";
                }
            }

            // C. Chart Temperatura + Umiditate
            if (tempChart && data.temp > 0) {
                const now = new Date().toLocaleTimeString();

                // Pastram doar ultimele 20 puncte
                if (tempChart.data.labels.length > 20) {
                    tempChart.data.labels.shift();
                    tempChart.data.datasets[0].data.shift(); // Temp
                    tempChart.data.datasets[1].data.shift(); // Hum
                }

                // Adaugam datele noi
                tempChart.data.labels.push(now);
                tempChart.data.datasets[0].data.push(data.temp); // Linie Verde

                // Verificam daca senzorul trimite umiditate, altfel punem 0
                const humVal = data.hum ? data.hum : 0;
                tempChart.data.datasets[1].data.push(humVal); // Linie Albastra

                // Zoom Dinamic doar pe Temp (Stanga)
                tempChart.options.scales.y.min = Math.floor(data.temp - 3);
                tempChart.options.scales.y.max = Math.ceil(data.temp + 3);

                // Umiditatea (Dreapta) ramane fixa 0-100

                tempChart.update();
            }
        })
        .catch(e => console.log("Așteptare server..."));
}, 1000);

// -- DRIVE LOGIC --
let lastDriveTs = 0;
const DRIVE_INTERVAL_MS = 70;
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
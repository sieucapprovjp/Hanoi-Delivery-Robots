function logEvent(message) {
    const el = document.getElementById('event-log');
    if (!el) return;
    
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="timestamp">[${new Date().toLocaleTimeString()}]</span>${message}`;
    el.insertBefore(entry, el.firstChild);
    
    while (el.children.length > 100) el.removeChild(el.lastChild);
}

function addDispatchInsight(message, tone = 'neutral') {
    const el = document.getElementById('dispatch-insights');
    if (!el) return;

    const entry = document.createElement('div');
    entry.className = `dispatch-entry ${tone}`;
    entry.innerHTML = `<span class="dispatch-time">${new Date().toLocaleTimeString()}</span><span class="dispatch-text">${message}</span>`;
    el.insertBefore(entry, el.firstChild);

    while (el.children.length > 20) el.removeChild(el.lastChild);
}

async function init() {
    simulation = new Simulation();
    await simulation.initialize();
    setupControls();
}

function setupControls() {
    document.getElementById('start-btn')?.addEventListener('click', () => simulation?.start());
    document.getElementById('pause-btn')?.addEventListener('click', () => simulation?.pause());
    document.getElementById('reset-btn')?.addEventListener('click', () => simulation?.reset());
    
    const slider = document.getElementById('speed-slider');
    const value = document.getElementById('speed-value');
    slider?.addEventListener('input', (e) => {
        const speed = parseInt(e.target.value);
        if (simulation) simulation.speed = speed;
        value.textContent = `${speed}x`;
    });

    document.getElementById('toggle-robots')?.addEventListener('click', () => {
        const p = document.querySelector('.robot-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });
    document.getElementById('toggle-deliveries')?.addEventListener('click', () => {
        const p = document.querySelector('.delivery-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });
    document.getElementById('toggle-log')?.addEventListener('click', () => {
        const p = document.querySelector('.log-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });
    document.getElementById('toggle-dispatch')?.addEventListener('click', () => {
        const p = document.querySelector('.dispatch-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });
    document.getElementById('toggle-analytics')?.addEventListener('click', () => {
        const p = document.querySelector('.analytics-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });

    document.getElementById('close-dispatch-panel')?.addEventListener('click', () => {
        const p = document.querySelector('.dispatch-panel');
        p.style.display = 'none';
    });
    document.getElementById('close-analytics-panel')?.addEventListener('click', () => {
        const p = document.querySelector('.analytics-panel');
        p.style.display = 'none';
    });
}

window.addEventListener('load', () => {
    init().catch(error => {
        console.error(error);
        logEvent('❌ Failed to initialize map routing');
    });
});

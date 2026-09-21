// IronEye Live Dashboard Telemetry & Stream Controller

let statusInterval = null;

// DOM Elements
const videoFeed = document.getElementById('videoFeed');
const btnStart = document.getElementById('btnStart');
const btnStop = document.getElementById('btnStop');
const btnRefresh = document.getElementById('btnRefresh');
const statusBadge = document.getElementById('statusBadge');
const pulseDot = document.getElementById('pulseDot');
const liveIndicatorText = document.getElementById('liveIndicatorText');
const videoSourceText = document.getElementById('videoSourceText');
const detectionCountEl = document.getElementById('detectionCount');
const detectedClassesList = document.getElementById('detectedClassesList');
const alertMissingVideo = document.getElementById('alertMissingVideo');
const sysClock = document.getElementById('sysClock');
const fpsVal = document.getElementById('fpsVal');

// Update Clock
function updateClock() {
  if (sysClock) {
    const now = new Date();
    sysClock.textContent = now.toTimeString().split(' ')[0] + ' UTC' + (now.getTimezoneOffset() > 0 ? '-' : '+') + Math.abs(now.getTimezoneOffset() / 60);
  }
}
setInterval(updateClock, 1000);
updateClock();

// Refresh stream connection if stalled
function reloadStream() {
  if (videoFeed) {
    const currentSrc = '/video_feed?t=' + Date.now();
    videoFeed.src = currentSrc;
  }
}

// Fetch status and update UI
async function fetchStatus() {
  try {
    const response = await fetch('/api/status');
    if (!response.ok) return;
    const data = await response.json();

    // Update Video Source
    if (videoSourceText) {
      videoSourceText.textContent = data.video_source || 'test.mp4';
    }

    // Update FPS
    if (fpsVal && data.fps !== undefined) {
      fpsVal.textContent = `${data.fps} FPS`;
    }

    // Update Detection Count
    if (detectionCountEl) {
      detectionCountEl.textContent = data.detection_count ?? 0;
    }

    // Update Missing Video Alert Banner
    if (alertMissingVideo) {
      if (!data.file_available) {
        alertMissingVideo.style.display = 'flex';
      } else {
        alertMissingVideo.style.display = 'none';
      }
    }

    // Update Status Badge & Pulse Indicator
    if (statusBadge && pulseDot && liveIndicatorText) {
      statusBadge.className = 'status-badge';
      pulseDot.className = 'pulse-dot';

      if (!data.file_available) {
        statusBadge.classList.add('status-error');
        statusBadge.textContent = 'MISSING VIDEO';
        pulseDot.classList.add('error');
        liveIndicatorText.textContent = 'FILE MISSING';
      } else if (!data.is_running) {
        statusBadge.classList.add('status-paused');
        statusBadge.textContent = 'STOPPED';
        pulseDot.classList.add('stopped');
        liveIndicatorText.textContent = 'STOPPED';
      } else {
        statusBadge.classList.add('status-active');
        statusBadge.textContent = 'MONITORING';
        pulseDot.classList.add('active');
        liveIndicatorText.textContent = 'MONITORING';
      }
    }

    // Update Detected Classes Breakdown
    if (detectedClassesList) {
      const classes = data.detected_classes || {};
      const keys = Object.keys(classes);

      if (keys.length === 0) {
        detectedClassesList.innerHTML = `
          <div class="detection-pill" style="opacity: 0.5;">
            <span>No objects detected</span>
            <span class="detection-pill-count">0</span>
          </div>
        `;
      } else {
        detectedClassesList.innerHTML = keys.map(k => `
          <div class="detection-pill">
            <span style="text-transform: capitalize;">${k}</span>
            <span class="detection-pill-count">${classes[k]}</span>
          </div>
        `).join('');
      }
    }

    // Update Button States
    if (btnStart && btnStop) {
      if (!data.is_running) {
        btnStart.disabled = false;
        btnStart.style.opacity = '1';
        btnStop.disabled = true;
        btnStop.style.opacity = '0.5';
      } else {
        btnStart.disabled = true;
        btnStart.style.opacity = '0.5';
        btnStop.disabled = false;
        btnStop.style.opacity = '1';
      }
    }

  } catch (err) {
    console.error('Failed to fetch status:', err);
  }
}

// Action: Start Monitoring
async function startMonitoring() {
  try {
    const res = await fetch('/api/start', { method: 'POST' });
    if (res.ok) {
      fetchStatus();
      reloadStream();
    }
  } catch (err) {
    console.error('Failed to start monitoring:', err);
  }
}

// Action: Stop Monitoring
async function stopMonitoring() {
  try {
    const res = await fetch('/api/stop', { method: 'POST' });
    if (res.ok) {
      fetchStatus();
    }
  } catch (err) {
    console.error('Failed to stop monitoring:', err);
  }
}

// Event Listeners
if (btnStart) btnStart.addEventListener('click', startMonitoring);
if (btnStop) btnStop.addEventListener('click', stopMonitoring);
if (btnRefresh) btnRefresh.addEventListener('click', reloadStream);

// Initialize telemetry polling
fetchStatus();
statusInterval = setInterval(fetchStatus, 1000);

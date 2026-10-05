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
// ==========================================
// Safety Zone Interactive Drawing
// ==========================================
function initSafetyZoneDrawing() {
  const zoneCanvas = document.getElementById("zoneCanvas");
  if (!zoneCanvas) {
    console.error("Safety zone canvas (#zoneCanvas) not found in DOM.");
    return;
  }

  const SVG_NS = "http://www.w3.org/2000/svg";
  let zonePoints = [];
  let isSaved = false;
  let lastWidth = 0;
  let lastHeight = 0;

  function updateZoneCanvasSize() {
    const rect = zoneCanvas.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return;
    }

    // Proportional scaling for points when container changes size
    if (lastWidth > 0 && lastHeight > 0 && (lastWidth !== rect.width || lastHeight !== rect.height)) {
      const scaleX = rect.width / lastWidth;
      const scaleY = rect.height / lastHeight;
      zonePoints = zonePoints.map(p => ({
        x: Math.round(p.x * scaleX),
        y: Math.round(p.y * scaleY)
      }));
    }

    lastWidth = rect.width;
    lastHeight = rect.height;

    zoneCanvas.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);
    drawZone();
  }

  function getSVGCoordinates(event) {
    const rect = zoneCanvas.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return { x: 0, y: 0 };
    }

    if (zoneCanvas.getScreenCTM && zoneCanvas.createSVGPoint) {
      const ctm = zoneCanvas.getScreenCTM();
      if (ctm) {
        const pt = zoneCanvas.createSVGPoint();
        pt.x = event.clientX;
        pt.y = event.clientY;
        const svgPt = pt.matrixTransform(ctm.inverse());
        return {
          x: Math.round(svgPt.x),
          y: Math.round(svgPt.y)
        };
      }
    }

    const viewBox = zoneCanvas.viewBox.baseVal;
    const vbWidth = (viewBox && viewBox.width > 0) ? viewBox.width : rect.width;
    const vbHeight = (viewBox && viewBox.height > 0) ? viewBox.height : rect.height;

    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    return {
      x: Math.round((mouseX / rect.width) * vbWidth),
      y: Math.round((mouseY / rect.height) * vbHeight)
    };
  }

  function drawZone() {
    zoneCanvas.innerHTML = "";

    if (zonePoints.length === 0) {
      return;
    }

    const pointsStr = zonePoints.map(p => `${p.x},${p.y}`).join(" ");

    // Connect points: polygon if 3+ points, polyline if 2 points
    if (zonePoints.length >= 3) {
      const polygon = document.createElementNS(SVG_NS, "polygon");
      polygon.setAttribute("points", pointsStr);
      polygon.setAttribute("fill", "rgba(255, 170, 0, 0.2)");
      polygon.setAttribute("stroke", "#ffb000");
      polygon.setAttribute("stroke-width", "2");
      polygon.setAttribute("stroke-linejoin", "round");
      zoneCanvas.appendChild(polygon);
    } else if (zonePoints.length === 2) {
      const polyline = document.createElementNS(SVG_NS, "polyline");
      polyline.setAttribute("points", pointsStr);
      polyline.setAttribute("fill", "none");
      polyline.setAttribute("stroke", "#ffb000");
      polyline.setAttribute("stroke-width", "2");
      polyline.setAttribute("stroke-linecap", "round");
      polyline.setAttribute("stroke-linejoin", "round");
      zoneCanvas.appendChild(polyline);
    }

    // Draw orange circular points
    zonePoints.forEach(p => {
      const circle = document.createElementNS(SVG_NS, "circle");
      circle.setAttribute("cx", p.x);
      circle.setAttribute("cy", p.y);
      circle.setAttribute("r", "5");
      circle.setAttribute("fill", "#ffb000");
      circle.setAttribute("stroke", "#ffffff");
      circle.setAttribute("stroke-width", "1.5");
      zoneCanvas.appendChild(circle);
    });
  }

  zoneCanvas.addEventListener("click", (event) => {
    // Prevent duplicate point creation from double-clicks
    if (event.detail > 1) {
      return;
    }

    // Reset when starting to draw a new zone after previous was saved
    if (isSaved) {
      zonePoints = [];
      isSaved = false;
    }

    const { x, y } = getSVGCoordinates(event);
    zonePoints.push({ x, y });
    drawZone();
  });

  zoneCanvas.addEventListener("dblclick", async (event) => {
    event.preventDefault();
    event.stopPropagation();

    // Remove any accidental duplicate point from the double-click sequence
    if (zonePoints.length >= 2) {
      const last = zonePoints[zonePoints.length - 1];
      const prev = zonePoints[zonePoints.length - 2];
      if (Math.hypot(last.x - prev.x, last.y - prev.y) < 10) {
        zonePoints.pop();
        drawZone();
      }
    }

    if (zonePoints.length < 3) {
      console.warn("Safety zone requires at least 3 points to close and save.");
      return;
    }

    try {
      const response = await fetch("/api/set_zone", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          points: zonePoints
        })
      });

      const result = await response.json();

      if (!response.ok) {
        console.error("Failed to save safety zone:", result.message || result || `HTTP ${response.status}`);
        return;
      }

      console.log("Safety zone saved successfully:", result);
      isSaved = true;
    } catch (error) {
      console.error("Safety zone request failed:", error);
    }
  });

  window.addEventListener("resize", updateZoneCanvasSize);

  if (window.ResizeObserver) {
    const observer = new ResizeObserver(() => {
      updateZoneCanvasSize();
    });
    observer.observe(zoneCanvas);
  }

  const videoFeedEl = document.getElementById("videoFeed");
  if (videoFeedEl) {
    videoFeedEl.addEventListener("load", updateZoneCanvasSize);
  }

  updateZoneCanvasSize();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initSafetyZoneDrawing);
} else {
  initSafetyZoneDrawing();
}
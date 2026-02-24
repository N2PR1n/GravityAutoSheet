// --- STATE ---
let allOrders = [];
let html5QrcodeScanner = null;
let recoveryQueue = [];
let isRecovering = false;
let currentFilterStatus = 'all'; // 'all', 'pending', 'checked'

// --- INIT ---
document.addEventListener('DOMContentLoaded', () => {
    fetchOrders();
    fetchSheets(true);
    fetchConfig();
    initScanner();

    // Search Listener
    document.getElementById('search-input').addEventListener('input', (e) => {
        filterOrders(e.target.value);
    });
});

// --- API ---
async function fetchOrders() {
    const listEl = document.getElementById('order-list');
    const countEl = document.getElementById('order-count');

    // Show Loading only if empty
    if (listEl.innerHTML.trim() === "") {
        listEl.innerHTML = `<div class="col-12 text-center py-5 text-muted"><div class="spinner-border text-primary"></div></div>`;
    }

    try {
        const res = await fetch('/api/orders');
        const data = await res.json();

        allOrders = data;
        applyFilters();

        // Start Auto Recovery for missing images
        startAutoRecovery(data);

    } catch (e) {
        console.error(e);
        listEl.innerHTML = `<div class="col-12 text-center text-danger">Failed to load orders. <button class="btn btn-sm btn-outline-danger" onclick="fetchOrders()">Retry</button></div>`;
    }
}

async function updateStatus(orderId, action) {
    if (!confirm(`Are you sure you want to ${action} this order?`)) return;

    try {
        const res = await fetch(`/api/orders/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId })
        });
        const result = await res.json();

        if (result.success) {
            showToast(`Order ${action}ed successfully!`);
            fetchOrders(); // Refresh
        } else {
            alert('Failed to update status.');
        }
    } catch (e) {
        console.error(e);
        alert('Error connecting to server.');
    }
}

// --- FILTER LOGIC ---
function setFilter(status) {
    currentFilterStatus = status;

    // Reset all buttons
    ['all', 'pending', 'checked', 'saved', 'cancelled'].forEach(s => {
        const btn = document.getElementById(`btn-filter-${s}`);
        if (btn) btn.classList.remove('active');
    });

    // Set Active
    const activeBtn = document.getElementById(`btn-filter-${status}`);
    if (activeBtn) activeBtn.classList.add('active');

    applyFilters();
}

function applyFilters() {
    const query = document.getElementById('search-input').value;
    filterOrders(query);
}


// --- RENDER ---
function renderOrders(orders) {
    const listEl = document.getElementById('order-list');
    listEl.innerHTML = '';

    if (orders.length === 0) {
        listEl.innerHTML = `<div class="col-12 text-center text-muted py-5">No orders found.</div>`;
        return;
    }

    const html = orders.map(order => {
        const rawStatus = (order['Status'] || 'Pending').toLowerCase().trim();
        let statusClass = 'status-pending';
        let statusLabel = order['Status'] || 'Pending';

        // Normalize Status
        if (rawStatus === 'checked') {
            statusClass = 'status-checked';
            statusLabel = 'Checked'; // Blue
        } else if (rawStatus === 'saved' || rawStatus === 'save') {
            statusClass = 'status-saved';
            statusLabel = 'Saved'; // Orange
        } else if (rawStatus.includes('cancel') || rawStatus === 'cancelled' || rawStatus === 'cancleed') {
            statusClass = 'status-cancelled';
            statusLabel = 'Cancelled'; // Red
            if (rawStatus === 'cancleed') statusLabel = 'Cancelled';
        } else {
            statusClass = 'status-pending'; // Yellow default
            statusLabel = 'Pending';
        }

        const isChecked = rawStatus === 'checked';
        const isPending = statusLabel.toLowerCase() === 'pending';

        let btnHtml = '';
        if (isChecked) {
            btnHtml = `<button class="btn btn-outline-danger w-100" onclick="updateStatus('${order['Order ID']}', 'uncheck')">❌ Uncheck</button>`;
        } else if (isPending) {
            btnHtml = `<button class="btn btn-info w-100 text-white" onclick="updateStatus('${order['Order ID']}', 'check')">✅ Check</button>`;
        }

        const btnLogin = btnHtml;

        // Image Handling
        let imgHtml = '';
        if (order.DirectImage) {
            imgHtml = `<img src="${order.DirectImage}" class="order-img" onclick="showImage('${order.DirectImage}')" loading="lazy">`;
        } else {
            // Placeholder with spinner or button
            imgHtml = `
                <div class="order-img d-flex flex-column justify-content-center align-items-center text-muted" id="img-box-${order['Order ID']}">
                    <span id="status-${order['Order ID']}">Checking...</span>
                    <!-- Button hidden by default if auto-recovery runs, but kept for backup -->
                    <button class="btn btn-sm btn-outline-secondary mt-2 d-none" id="btn-${order['Order ID']}" onclick="recoverImage('${order['Order ID']}', '${order['Run No']}')">🔄 Find</button>
                    ${order.RawImageLink ? `<small class="d-none">${order.RawImageLink}</small>` : ''}
                </div>
            `;
        }

        // Platform Logo Logic
        const platform = (order['Platform'] || '').toLowerCase().trim();
        let platformLogo = '';
        if (platform.includes('lazada')) {
            platformLogo = '<img src="/static/img/lazada.png" style="height: 24px; vertical-align: middle;" alt="Lazada">';
        } else if (platform.includes('shopee')) {
            platformLogo = '<img src="/static/img/shopee.png" style="height: 24px; vertical-align: middle;" alt="Shopee">';
        } else if (platform.includes('tiktok')) {
            platformLogo = '<img src="/static/img/tiktok.png" style="height: 24px; vertical-align: middle;" alt="TikTok">';
        } else if (platform.includes('line')) {
            platformLogo = '<img src="/static/img/line.png" style="height: 24px; vertical-align: middle;" alt="Line">';
        } else if (platform.includes('amaze')) {
            platformLogo = '<img src="/static/img/Amaze.png" style="height: 24px; vertical-align: middle;" alt="Amaze">';
        } else {
            platformLogo = '🛒 ' + (order['Platform'] || 'Unknown');
        }

        const card = `
            <div class="col-12 col-md-6 col-lg-4">
                <div class="order-card h-100 card-${statusClass.replace('status-', '')}">
                    <div class="card-header-custom d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center">
                           <span class="run-no me-2">${order['Run No'] || '-'}</span>
                           ${platformLogo}
                        </div>
                        <span class="badge badge-status ${statusClass}">${statusLabel}</span>
                    </div>
                    
                    <div class="row g-2 mt-2">
                        <div class="col-4">
                            ${imgHtml}
                        </div>
                        <div class="col-8">
                            <div class="detail-row"><b>👤 Name:</b> ${order['Name'] || '-'}</div>
                            <div class="detail-row"><b>📍 Loc:</b> ${order['Location'] || '-'}</div>
                            <div class="detail-row"><b>📦 Item:</b> ${order['Item'] || '-'}</div>
                            <div class="detail-row text-truncate"><b>💰 Price:</b> <b style="color: #ff4500; font-size: 1.05em;">${order['Price']}</b> | <b style="color: #daa520;">🪙 ${order['Coins']}</b></div>
                            <div class="detail-row"><small class="text-muted">Date: ${order['Date']}</small></div>
                            
                            <div class="mt-2 pt-2 border-top border-secondary">
                                ${btnLogin}
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-2 text-muted small text-truncate">
                        ID: ${order['Order ID']}<br>
                        Tracking: ${order['Tracking']}
                    </div>
                </div>
            </div>
        `;
        return card;
    }).join('');

    listEl.innerHTML = html;
}

function filterOrders(query) {
    if (!query && currentFilterStatus === 'all') {
        renderOrders(allOrders);
        document.getElementById('order-count').innerText = allOrders.length;
        return;
    }

    query = (query || '').toString().toLowerCase().trim();

    const filtered = allOrders.filter(o => {
        // 1. Text Search
        const name = (o['Name'] || '').toString().toLowerCase();
        const oid = (o['Order ID'] || '').toString().toLowerCase();
        const runNo = (o['Run No'] || '').toString().toLowerCase();
        const track = (o['Tracking'] || '').toString().toLowerCase();
        const item = (o['Item'] || '').toString().toLowerCase();

        const matchesText = name.includes(query) ||
            oid.includes(query) ||
            runNo.includes(query) ||
            track.includes(query) ||
            item.includes(query);

        if (!matchesText) return false;

        // 2. Status Filter
        if (currentFilterStatus === 'all') return true;

        const rawStatus = (o['Status'] || 'pending').toLowerCase().trim();

        if (currentFilterStatus === 'checked') return rawStatus === 'checked';
        if (currentFilterStatus === 'saved') return rawStatus === 'saved';
        if (currentFilterStatus === 'cancelled') return rawStatus.includes('cancel');

        if (currentFilterStatus === 'pending') {
            // Pending means NOT Checked, NOT Saved, NOT Cancelled
            return rawStatus !== 'checked' && rawStatus !== 'saved' && !rawStatus.includes('cancel');
        }

        return true;
    });

    document.getElementById('order-count').innerText = filtered.length;
    renderOrders(filtered);
}

function startAutoRecovery(orders) {
    // Filter orders needing recovery
    const needingRecovery = orders.filter(o => !o.DirectImage);
    recoveryQueue = needingRecovery.map(o => ({ id: o['Order ID'], runNo: o['Run No'] }));

    if (!isRecovering && recoveryQueue.length > 0) {
        processRecoveryQueue();
    }
}

async function processRecoveryQueue() {
    if (recoveryQueue.length === 0) {
        isRecovering = false;
        return;
    }

    isRecovering = true;
    const task = recoveryQueue.shift(); // Get next

    await recoverImage(task.id, task.runNo, true); // true = auto mode

    // Add delay to prevent rate limit (e.g., 500ms)
    setTimeout(processRecoveryQueue, 500);
}

async function recoverImage(orderId, runNo, isAuto = false) {
    const box = document.getElementById(`img-box-${orderId}`);
    const statusEl = document.getElementById(`status-${orderId}`);
    const btnEl = document.getElementById(`btn-${orderId}`);

    if (statusEl) statusEl.innerText = "Searching...";
    if (btnEl) btnEl.classList.add('d-none'); // Hide button while searching

    // Use Run No for recovery if available, fallback to Order ID
    const target = runNo || orderId;

    try {
        const res = await fetch(`/api/find_image/${target}`);
        const data = await res.json();

        if (data.found && data.url) {
            // Update Data model
            const order = allOrders.find(o => o['Order ID'] == orderId);
            if (order) order.DirectImage = data.url;

            // Re-render box
            if (box) {
                box.parentElement.innerHTML = `<img src="${data.url}" class="order-img" onclick="showImage('${data.url}')">`;
            }
        } else {
            if (statusEl) statusEl.innerText = "No Image";
            if (btnEl) btnEl.classList.remove('d-none'); // Show button to retry
        }
    } catch (e) {
        if (statusEl) statusEl.innerText = "Error";
        if (btnEl) btnEl.classList.remove('d-none');
    }
}

function showImage(url) {
    document.getElementById('full-image').src = url;
    new bootstrap.Modal(document.getElementById('imageModal')).show();
}

function showToast(msg) {
    document.getElementById('toast-msg').innerText = msg;
    const toast = new bootstrap.Toast(document.getElementById('liveToast'));
    toast.show();
}

// --- SCANNER ---
function initScanner() {
    // We do NOT init scanner on load anymore.
    // We init it when Modal opens.

    const scannerModal = document.getElementById('scannerModal');
    scannerModal.addEventListener('shown.bs.modal', startScanner);
    scannerModal.addEventListener('hidden.bs.modal', stopScanner);
}

function startScanner() {
    if (html5QrcodeScanner) {
        // Already running
        return;
    }

    // Custom config for long barcodes (Rectangle)
    const config = {
        fps: 20,
        qrbox: { width: 300, height: 150 },
        aspectRatio: 1.0,
        experimentalFeatures: {
            useBarCodeDetectorIfSupported: true
        }
    };

    // Clear reader element just in case
    document.getElementById('reader').innerHTML = "";

    html5QrcodeScanner = new Html5QrcodeScanner(
        "reader", config, /* verbose= */ false);

    html5QrcodeScanner.render(onScanSuccess, onScanError);
}

function stopScanner() {
    if (html5QrcodeScanner) {
        html5QrcodeScanner.clear().catch(error => {
            console.error("Failed to clear scanner", error);
        }).finally(() => {
            html5QrcodeScanner = null;
        });
    }
}

function onScanSuccess(decodedText, decodedResult) {
    console.log(`Scan matched: ${decodedText}`);

    // Stop scanner first to prevent double scan or errors during close
    // Actually, let's just close modal, and let the 'hidden.bs.modal' event handle the stop.

    // Close Modal
    const modalEl = document.getElementById('scannerModal');
    const modalInstance = bootstrap.Modal.getInstance(modalEl);
    if (modalInstance) modalInstance.hide();

    // Set Search
    const searchInput = document.getElementById('search-input');
    searchInput.value = decodedText;
    filterOrders(decodedText);

    showToast(`Scanned: ${decodedText}`);
}

function onScanError(errorMessage) {
    // parse error, ignore loop
}

// --- Sheet Logic ---
async function fetchSheets(isFirstLoad = false) {
    try {
        const response = await fetch('/api/sheets');
        const data = await response.json();

        if (data.sheets) {
            const listEl = document.getElementById('sheet-list-dropdown');
            const currentEl = document.getElementById('current-sheet-name');
            const pinnedSheet = localStorage.getItem('pinnedSheet');

            // Set Current
            if (data.current) {
                currentEl.innerText = data.current;
            }

            // Auto-switch if pinned and first load
            if (isFirstLoad && pinnedSheet && data.sheets.includes(pinnedSheet) && data.current !== pinnedSheet) {
                console.log("Auto-switching to pinned sheet:", pinnedSheet);
                switchSheet(pinnedSheet);
                return;
            }

            // Populate List
            listEl.innerHTML = `<li><h6 class="dropdown-header small text-uppercase fw-bold text-muted">Select Month / Sheet</h6></li>`;

            data.sheets.forEach(sheet => {
                const isActive = sheet === data.current;
                const activeClass = isActive ? 'active text-primary bg-primary-subtle' : '';
                const isPinned = sheet === pinnedSheet;

                const li = document.createElement('li');
                li.className = "mb-1";
                li.innerHTML = `
                    <div class="dropdown-item ${activeClass} d-flex justify-content-between align-items-center">
                        <span class="flex-grow-1 cursor-pointer fw-medium" onclick="switchSheet('${sheet}')" style="font-size: 0.95rem;">${sheet}</span>
                        <button class="pin-btn ${isPinned ? 'pinned' : 'unpinned'}" onclick="togglePin(event, '${sheet}')" title="${isPinned ? 'Unpin' : 'Pin this sheet'}">
                            ●
                        </button>
                    </div>
                `;
                listEl.appendChild(li);
            });
        }
    } catch (e) {
        console.error("Error fetching sheets:", e);
    }
}

function togglePin(event, sheetName) {
    event.stopPropagation();
    const currentPinned = localStorage.getItem('pinnedSheet');

    if (currentPinned === sheetName) {
        localStorage.removeItem('pinnedSheet');
        showToast(`Unpinned ${sheetName}`);
    } else {
        localStorage.setItem('pinnedSheet', sheetName);
        showToast(`Pinned ${sheetName}`);
    }

    fetchSheets(); // Re-render dropdown
}

async function switchSheet(sheetName) {
    try {
        document.getElementById('current-sheet-name').innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div>';

        const response = await fetch('/api/set_sheet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sheet_name: sheetName })
        });

        const result = await response.json();
        if (result.success) {
            showToast(`Switched to ${sheetName}`);
            await fetchSheets(); // Refresh UI
            await fetchOrders(); // Reload Data
        } else {
            showToast('Failed to switch sheet');
            fetchSheets(); // Reset UI
        }
    } catch (e) {
        console.error("Error switching sheet:", e);
        showToast('Error switching sheet');
    }
}

// --- Config Logic ---
async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        if (data.GOOGLE_DRIVE_FOLDER_ID) {
            document.getElementById('folder-id-input').value = data.GOOGLE_DRIVE_FOLDER_ID;
        }
    } catch (e) {
        console.error("Error fetching config:", e);
    }
}

async function saveConfig() {
    const folderId = document.getElementById('folder-id-input').value.trim();
    if (!folderId) {
        alert("Please enter a valid Folder ID.");
        return;
    }

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_id: folderId })
        });

        const result = await response.json();
        if (result.success) {
            showToast("Settings saved successfully!");
            bootstrap.Modal.getInstance(document.getElementById('settingsModal')).hide();
        } else {
            showToast("Failed to save settings.");
        }
    } catch (e) {
        console.error("Error saving config:", e);
        showToast("Error saving settings.");
    }
}

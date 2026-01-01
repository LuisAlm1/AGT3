/**
 * Dashboard JavaScript - MarketingBot SaaS
 */

// ============================================
// STATE
// ============================================
const state = {
    user: null,
    posts: [],
    credits: 0,
    currentView: 'chat',
    currentMonth: new Date(),
    isLoading: false
};

// ============================================
// DOM ELEMENTS
// ============================================
const elements = {
    // Views
    chatView: document.getElementById('chatView'),
    calendarView: document.getElementById('calendarView'),
    postsView: document.getElementById('postsView'),
    creditsView: document.getElementById('creditsView'),
    settingsView: document.getElementById('settingsView'),

    // Chat
    chatMessages: document.getElementById('chatMessages'),
    chatForm: document.getElementById('chatForm'),
    chatInput: document.getElementById('chatInput'),
    sendBtn: document.getElementById('sendBtn'),

    // Calendar
    calendarMonth: document.getElementById('calendarMonth'),
    calendarDays: document.getElementById('calendarDays'),
    prevMonth: document.getElementById('prevMonth'),
    nextMonth: document.getElementById('nextMonth'),

    // Posts
    postsList: document.getElementById('postsList'),
    scheduleMoreBtn: document.getElementById('scheduleMoreBtn'),

    // Credits
    creditsBalance: document.getElementById('creditsBalance'),
    balanceAmount: document.getElementById('balanceAmount'),
    packagesGrid: document.getElementById('packagesGrid'),
    historyList: document.getElementById('historyList'),

    // Settings
    businessSummary: document.getElementById('businessSummary'),
    postStyle: document.getElementById('postStyle'),
    connectedPage: document.getElementById('connectedPage'),
    currentRecurrence: document.getElementById('currentRecurrence'),
    preferredTime: document.getElementById('preferredTime'),
    changePageBtn: document.getElementById('changePageBtn'),

    // Header
    viewTitle: document.getElementById('viewTitle'),
    userName: document.getElementById('userName'),
    pageName: document.getElementById('pageName'),

    // Modals
    pageModal: document.getElementById('pageModal'),
    closePageModal: document.getElementById('closePageModal'),
    pagesList: document.getElementById('pagesList'),
    postModal: document.getElementById('postModal'),
    closePostModal: document.getElementById('closePostModal'),
    postModalBody: document.getElementById('postModalBody')
};

// ============================================
// API HELPERS
// ============================================
async function api(endpoint, options = {}) {
    const response = await fetch(`/api${endpoint}`, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || 'Error en la petición');
    }

    return response.json();
}

// ============================================
// INITIALIZATION
// ============================================
async function init() {
    try {
        // Load user profile
        await loadUserProfile();

        // Load initial data
        await Promise.all([
            loadChatHistory(),
            loadPosts(),
            loadCredits()
        ]);

        // Setup event listeners
        setupEventListeners();

        // Render initial view
        renderCalendar();

    } catch (error) {
        console.error('Error initializing:', error);
    }
}

async function loadUserProfile() {
    try {
        const data = await api('/user/profile');
        state.user = data;

        // Update UI
        elements.userName.textContent = data.name || 'Usuario';
        if (data.facebook_page_name) {
            elements.pageName.textContent = data.facebook_page_name;
            elements.pageName.style.display = 'inline-block';
        }

        // Settings
        elements.businessSummary.value = data.business_summary || '';
        elements.postStyle.value = data.post_style || '';
        elements.connectedPage.textContent = data.facebook_page_name || 'No conectada';

        const recurrenceLabels = {
            'daily': 'Diaria',
            'weekly': 'Semanal',
            'biweekly': 'Quincenal',
            'monthly': 'Mensual'
        };
        elements.currentRecurrence.textContent = recurrenceLabels[data.posting_recurrence] || '--';
        elements.preferredTime.textContent = data.preferred_posting_time || '--';

    } catch (error) {
        console.error('Error loading profile:', error);
    }
}

async function loadChatHistory() {
    try {
        const data = await api('/chat/history');

        if (data.messages && data.messages.length > 0) {
            // Clear welcome message
            const welcome = elements.chatMessages.querySelector('.welcome-message');
            if (welcome) welcome.remove();

            // Add messages
            data.messages.forEach(msg => {
                addMessageToUI(msg.role, msg.content);
            });

            scrollToBottom();
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

async function loadPosts() {
    try {
        const data = await api('/posts');
        state.posts = data.posts || [];
        renderPosts();
    } catch (error) {
        console.error('Error loading posts:', error);
    }
}

async function loadCredits() {
    try {
        const data = await api('/credits/balance');
        state.credits = data.balance;
        updateCreditsUI();

        // Load packages
        const packagesData = await api('/credits/packages');
        renderPackages(packagesData.packages);

        // Load history
        const historyData = await api('/credits/history');
        renderCreditHistory(historyData.history);

    } catch (error) {
        console.error('Error loading credits:', error);
    }
}

// ============================================
// EVENT LISTENERS
// ============================================
function setupEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = item.dataset.view;
            switchView(view);
        });
    });

    // Chat form
    elements.chatForm.addEventListener('submit', handleChatSubmit);

    // Auto-resize textarea
    elements.chatInput.addEventListener('input', autoResizeTextarea);

    // Calendar navigation
    elements.prevMonth.addEventListener('click', () => {
        state.currentMonth.setMonth(state.currentMonth.getMonth() - 1);
        renderCalendar();
    });

    elements.nextMonth.addEventListener('click', () => {
        state.currentMonth.setMonth(state.currentMonth.getMonth() + 1);
        renderCalendar();
    });

    // Schedule more posts
    elements.scheduleMoreBtn.addEventListener('click', scheduleMorePosts);

    // Change page button
    elements.changePageBtn.addEventListener('click', openPageModal);

    // Modal close buttons
    elements.closePageModal.addEventListener('click', () => {
        elements.pageModal.classList.remove('active');
    });

    elements.closePostModal.addEventListener('click', () => {
        elements.postModal.classList.remove('active');
    });

    // Close modals on backdrop click
    elements.pageModal.addEventListener('click', (e) => {
        if (e.target === elements.pageModal) {
            elements.pageModal.classList.remove('active');
        }
    });

    elements.postModal.addEventListener('click', (e) => {
        if (e.target === elements.postModal) {
            elements.postModal.classList.remove('active');
        }
    });
}

// ============================================
// VIEW SWITCHING
// ============================================
function switchView(viewName) {
    state.currentView = viewName;

    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewName);
    });

    // Update views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });

    const viewElement = document.getElementById(`${viewName}View`);
    if (viewElement) {
        viewElement.classList.add('active');
    }

    // Update title
    const titles = {
        chat: 'Asistente',
        calendar: 'Calendario',
        posts: 'Mis Posts',
        credits: 'Créditos',
        settings: 'Configuración'
    };
    elements.viewTitle.textContent = titles[viewName] || viewName;

    // Refresh data if needed
    if (viewName === 'calendar') {
        renderCalendar();
    } else if (viewName === 'posts') {
        loadPosts();
    } else if (viewName === 'credits') {
        loadCredits();
    }
}

// ============================================
// CHAT FUNCTIONALITY
// ============================================
async function handleChatSubmit(e) {
    e.preventDefault();

    const message = elements.chatInput.value.trim();
    if (!message || state.isLoading) return;

    // Clear input
    elements.chatInput.value = '';
    autoResizeTextarea();

    // Remove welcome message if present
    const welcome = elements.chatMessages.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    // Add user message
    addMessageToUI('user', message);
    scrollToBottom();

    // Show typing indicator
    const typingId = showTypingIndicator();

    state.isLoading = true;
    elements.sendBtn.disabled = true;

    try {
        const response = await api('/chat', {
            method: 'POST',
            body: JSON.stringify({ message })
        });

        // Remove typing indicator
        removeTypingIndicator(typingId);

        // Add assistant message
        if (response.message) {
            addMessageToUI('assistant', response.message);
        }

        // Handle function results
        if (response.function_results && response.function_results.length > 0) {
            response.function_results.forEach(result => {
                if (result.success) {
                    // Refresh data based on what was updated
                    loadUserProfile();
                    if (result.posts_scheduled) {
                        loadPosts();
                    }
                }
            });
        }

        // Check if onboarded
        if (response.is_onboarded) {
            loadPosts();
        }

        scrollToBottom();

    } catch (error) {
        removeTypingIndicator(typingId);
        addMessageToUI('assistant', 'Lo siento, hubo un error. Por favor intenta de nuevo.');
        console.error('Chat error:', error);
    } finally {
        state.isLoading = false;
        elements.sendBtn.disabled = false;
    }
}

function addMessageToUI(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const paragraph = document.createElement('p');
    paragraph.textContent = content;
    contentDiv.appendChild(paragraph);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);

    elements.chatMessages.appendChild(messageDiv);
}

function showTypingIndicator() {
    const id = 'typing-' + Date.now();
    const indicator = document.createElement('div');
    indicator.id = id;
    indicator.className = 'message assistant';
    indicator.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    elements.chatMessages.appendChild(indicator);
    scrollToBottom();
    return id;
}

function removeTypingIndicator(id) {
    const indicator = document.getElementById(id);
    if (indicator) indicator.remove();
}

function scrollToBottom() {
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function autoResizeTextarea() {
    elements.chatInput.style.height = 'auto';
    elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 150) + 'px';
}

// ============================================
// CALENDAR FUNCTIONALITY
// ============================================
function renderCalendar() {
    const year = state.currentMonth.getFullYear();
    const month = state.currentMonth.getMonth();

    // Update header
    const monthNames = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];
    elements.calendarMonth.textContent = `${monthNames[month]} ${year}`;

    // Get first day of month and total days
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const daysInPrevMonth = new Date(year, month, 0).getDate();

    // Create days HTML
    let html = '';
    const today = new Date();

    // Previous month days
    for (let i = firstDay - 1; i >= 0; i--) {
        const day = daysInPrevMonth - i;
        html += `<div class="calendar-day other-month">${day}</div>`;
    }

    // Current month days
    for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(year, month, day);
        const isToday = date.toDateString() === today.toDateString();
        const post = getPostForDate(date);

        let classes = 'calendar-day';
        if (isToday) classes += ' today';
        if (post) {
            classes += ` has-post ${post.status}`;
        }

        html += `<div class="${classes}" data-date="${date.toISOString()}">${day}</div>`;
    }

    // Next month days
    const totalCells = firstDay + daysInMonth;
    const remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (let i = 1; i <= remainingCells; i++) {
        html += `<div class="calendar-day other-month">${i}</div>`;
    }

    elements.calendarDays.innerHTML = html;

    // Add click listeners to days with posts
    elements.calendarDays.querySelectorAll('.calendar-day.has-post').forEach(day => {
        day.addEventListener('click', () => {
            const date = new Date(day.dataset.date);
            const post = getPostForDate(date);
            if (post) openPostModal(post);
        });
    });
}

function getPostForDate(date) {
    return state.posts.find(post => {
        const postDate = new Date(post.scheduled_at);
        return postDate.toDateString() === date.toDateString();
    });
}

// ============================================
// POSTS FUNCTIONALITY
// ============================================
function renderPosts() {
    if (state.posts.length === 0) {
        elements.postsList.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📄</span>
                <p>No hay posts programados todavía</p>
            </div>
        `;
        return;
    }

    const html = state.posts.map(post => {
        const date = new Date(post.scheduled_at);
        const formattedDate = date.toLocaleDateString('es-MX', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        const statusLabels = {
            'scheduled': 'Programado',
            'generating': 'Generando...',
            'ready': 'Listo',
            'posting': 'Publicando...',
            'posted': 'Publicado',
            'failed': 'Error'
        };

        return `
            <div class="post-card" data-id="${post.id}">
                <div class="post-image">
                    ${post.image_url ? `<img src="${post.image_url}" alt="Post image">` : '<div class="placeholder"></div>'}
                </div>
                <div class="post-info">
                    <div class="post-date">${formattedDate}</div>
                    <div class="post-caption">${post.caption || 'Caption pendiente de generar'}</div>
                    <span class="post-status ${post.status}">${statusLabels[post.status] || post.status}</span>
                </div>
                <div class="post-actions">
                    ${post.status === 'scheduled' ? `
                        <button class="btn btn-sm btn-outline" onclick="cancelPost('${post.id}')">Cancelar</button>
                    ` : ''}
                    ${post.facebook_post_url ? `
                        <a href="${post.facebook_post_url}" target="_blank" class="btn btn-sm btn-primary">Ver en FB</a>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');

    elements.postsList.innerHTML = html;
}

async function scheduleMorePosts() {
    try {
        elements.scheduleMoreBtn.disabled = true;
        elements.scheduleMoreBtn.textContent = 'Programando...';

        await api('/posts/schedule', { method: 'POST' });
        await loadPosts();

    } catch (error) {
        console.error('Error scheduling posts:', error);
        alert('Error al programar posts: ' + error.message);
    } finally {
        elements.scheduleMoreBtn.disabled = false;
        elements.scheduleMoreBtn.textContent = 'Programar más';
    }
}

async function cancelPost(postId) {
    if (!confirm('¿Estás seguro de cancelar este post?')) return;

    try {
        await api(`/posts/${postId}/cancel`, { method: 'DELETE' });
        await loadPosts();
        renderCalendar();
    } catch (error) {
        console.error('Error canceling post:', error);
        alert('Error al cancelar: ' + error.message);
    }
}

function openPostModal(post) {
    const date = new Date(post.scheduled_at);
    const formattedDate = date.toLocaleDateString('es-MX', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });

    elements.postModalBody.innerHTML = `
        <div style="text-align: center; margin-bottom: 1rem;">
            ${post.image_url ? `<img src="${post.image_url}" style="max-width: 100%; border-radius: 8px;">` : '<div style="height: 200px; background: #f3f4f6; border-radius: 8px;"></div>'}
        </div>
        <p><strong>Fecha:</strong> ${formattedDate}</p>
        <p><strong>Estado:</strong> ${post.status}</p>
        ${post.caption ? `<p><strong>Caption:</strong> ${post.caption}</p>` : ''}
        ${post.error_message ? `<p style="color: #ef4444;"><strong>Error:</strong> ${post.error_message}</p>` : ''}
        ${post.facebook_post_url ? `<p><a href="${post.facebook_post_url}" target="_blank" class="btn btn-primary" style="margin-top: 1rem;">Ver en Facebook</a></p>` : ''}
    `;

    elements.postModal.classList.add('active');
}

// ============================================
// CREDITS FUNCTIONALITY
// ============================================
function updateCreditsUI() {
    elements.creditsBalance.textContent = state.credits.toFixed(1);
    elements.balanceAmount.textContent = state.credits.toFixed(1);
}

function renderPackages(packages) {
    elements.packagesGrid.innerHTML = packages.map(pkg => `
        <div class="package-card" data-package="${pkg.name}">
            <div class="package-name">${pkg.name}</div>
            <div class="package-credits">${pkg.credits}</div>
            <div class="package-posts">${pkg.posts} posts</div>
            <div class="package-price">$${pkg.price_usd.toFixed(2)} USD</div>
        </div>
    `).join('');

    // Add click listeners
    elements.packagesGrid.querySelectorAll('.package-card').forEach(card => {
        card.addEventListener('click', () => {
            alert('Integración con Stripe próximamente. Contacta soporte para comprar créditos.');
        });
    });
}

function renderCreditHistory(history) {
    if (!history || history.length === 0) {
        elements.historyList.innerHTML = '<p style="color: #6b7280; text-align: center;">Sin transacciones aún</p>';
        return;
    }

    elements.historyList.innerHTML = history.map(item => {
        const date = new Date(item.created_at);
        const formattedDate = date.toLocaleDateString('es-MX', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });

        return `
            <div class="history-item">
                <div>
                    <div class="history-desc">${item.description}</div>
                    <div class="history-date">${formattedDate}</div>
                </div>
                <div class="history-amount ${item.amount > 0 ? 'positive' : 'negative'}">
                    ${item.amount > 0 ? '+' : ''}${item.amount.toFixed(1)}
                </div>
            </div>
        `;
    }).join('');
}

// ============================================
// PAGE SELECTION
// ============================================
async function openPageModal() {
    try {
        const data = await api('/user/pages');

        if (!data.pages || data.pages.length === 0) {
            elements.pagesList.innerHTML = '<p style="text-align: center; color: #6b7280;">No tienes páginas disponibles</p>';
        } else {
            elements.pagesList.innerHTML = data.pages.map(page => `
                <div class="page-option" data-id="${page.id}">
                    <div class="page-option-icon">
                        ${page.picture?.data?.url ? `<img src="${page.picture.data.url}">` : ''}
                    </div>
                    <div class="page-option-name">${page.name}</div>
                </div>
            `).join('');

            // Add click listeners
            elements.pagesList.querySelectorAll('.page-option').forEach(option => {
                option.addEventListener('click', () => selectPage(option.dataset.id));
            });
        }

        elements.pageModal.classList.add('active');

    } catch (error) {
        console.error('Error loading pages:', error);
        alert('Error al cargar páginas: ' + error.message);
    }
}

async function selectPage(pageId) {
    try {
        await api('/user/select-page', {
            method: 'POST',
            body: JSON.stringify({ page_id: pageId })
        });

        await loadUserProfile();
        elements.pageModal.classList.remove('active');

    } catch (error) {
        console.error('Error selecting page:', error);
        alert('Error al seleccionar página: ' + error.message);
    }
}

// ============================================
// INITIALIZE
// ============================================
document.addEventListener('DOMContentLoaded', init);

// Export functions for inline handlers
window.cancelPost = cancelPost;

/**
 * TrustCheck - Frontend JavaScript
 */

// Utility functions
const TrustCheck = {
    // Format date
    formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    // Format percentage
    formatPercent(value) {
        return (value * 100).toFixed(1) + '%';
    },

    // Show loading state
    showLoading(element) {
        element.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    },

    // Show alert
    showAlert(message, type = 'info') {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = message;

        const container = document.querySelector('.main-content .container');
        container.insertBefore(alert, container.firstChild);

        setTimeout(() => alert.remove(), 5000);
    },

    // API call helper
    async api(endpoint, options = {}) {
        try {
            const response = await fetch(`/api${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // Trigger scraper
    async triggerScraper(source) {
        try {
            const data = await this.api('/admin/scrape', {
                method: 'POST',
                body: JSON.stringify({ source })
            });
            this.showAlert(`Scrape triggered for ${source}`, 'success');
            return data;
        } catch (error) {
            this.showAlert(`Failed to trigger scrape: ${error.message}`, 'danger');
            throw error;
        }
    },

    // Clear cache
    async clearCache() {
        try {
            await this.api('/admin/cache/clear', { method: 'POST' });
            this.showAlert('Cache cleared successfully', 'success');
        } catch (error) {
            this.showAlert(`Failed to clear cache: ${error.message}`, 'danger');
        }
    },

    // Screen name via API
    async screenName(name, threshold = 0.8) {
        try {
            const data = await this.api('/screen', {
                method: 'POST',
                body: JSON.stringify({
                    name,
                    threshold,
                    max_results: 50
                })
            });
            return data;
        } catch (error) {
            this.showAlert(`Screening failed: ${error.message}`, 'danger');
            throw error;
        }
    },

    // Initialize dashboard charts if chart library is loaded
    initDashboardCharts(stats) {
        // Simple implementation without external chart library
        // Could be enhanced with Chart.js if needed
        console.log('Dashboard stats:', stats);
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    // Add click handlers for scraper buttons
    document.querySelectorAll('[data-scrape]').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const source = btn.dataset.scrape;
            btn.disabled = true;
            btn.textContent = 'Starting...';

            try {
                await TrustCheck.triggerScraper(source);
                btn.textContent = 'Started';
            } catch (error) {
                btn.textContent = 'Failed';
            }

            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = `Scrape ${source}`;
            }, 3000);
        });
    });

    // Add click handler for cache clear button
    const clearCacheBtn = document.querySelector('[data-clear-cache]');
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            await TrustCheck.clearCache();
        });
    }

    // Auto-refresh for admin page
    if (window.location.pathname === '/admin') {
        setInterval(() => {
            // Could refresh status here
        }, 30000);
    }

    // Handle screening form submission via AJAX (optional enhancement)
    const screeningForm = document.querySelector('#screening-form');
    if (screeningForm) {
        // Form already submits via POST, but could be enhanced with AJAX
    }

    console.log('TrustCheck UI initialized');
});

// Export for use in templates
window.TrustCheck = TrustCheck;

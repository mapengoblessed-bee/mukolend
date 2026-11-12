// Chart.js Visualisations for MukoLend Power BI-Style Analytics

function initAnalyticsCharts(chartsData) {
    if (!window.Chart || !chartsData) return;

    // Palette Definition (Bordeaux Silk & Silver Dust)
    const BORDEAUX = '#50222D';
    const BORDEAUX_LIGHT = '#7D3747';
    const SILVER = '#C4C3D0';
    const SILVER_DARK = '#8F8E9C';
    const ACCENT_EMERALD = '#059669';
    const ACCENT_AMBER = '#D97706';
    const ACCENT_ROSE = '#E11D48';

    // Global Font Settings
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = '#4A5568';

    // 1. Chart: Loan Requests Over Time
    const ctxRequests = document.getElementById('chartRequestsOverTime');
    if (ctxRequests && chartsData.requests_over_time) {
        new Chart(ctxRequests, {
            type: 'line',
            data: {
                labels: chartsData.requests_over_time.map(r => r.req_date),
                datasets: [{
                    label: 'Requests Count',
                    data: chartsData.requests_over_time.map(r => r.count),
                    borderColor: BORDEAUX,
                    backgroundColor: 'rgba(80, 34, 45, 0.08)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2.5,
                    pointRadius: 4,
                    pointBackgroundColor: BORDEAUX
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    // 2. Chart: Loan Status Distribution
    const ctxStatus = document.getElementById('chartStatusDistribution');
    if (ctxStatus && chartsData.status_distribution) {
        const labelsMap = {
            'pending': 'Pending',
            'accepted': 'Accepted',
            'awaiting_agreement': 'Awaiting Agreement',
            'active': 'Active',
            'repaid': 'Repaid',
            'overdue': 'Overdue',
            'cancelled': 'Cancelled'
        };
        const colorMap = {
            'pending': '#F59E0B',
            'accepted': '#3B82F6',
            'awaiting_agreement': SILVER_DARK,
            'active': '#6366F1',
            'repaid': ACCENT_EMERALD,
            'overdue': ACCENT_ROSE,
            'cancelled': '#9CA3AF'
        };

        new Chart(ctxStatus, {
            type: 'doughnut',
            data: {
                labels: chartsData.status_distribution.map(s => labelsMap[s.status] || s.status),
                datasets: [{
                    data: chartsData.status_distribution.map(s => s.count),
                    backgroundColor: chartsData.status_distribution.map(s => colorMap[s.status] || BORDEAUX_LIGHT),
                    borderWidth: 2,
                    borderColor: '#FFFFFF'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } }
                },
                cutout: '65%'
            }
        });
    }

    // 3. Chart: Loan Value by Community
    const ctxValComm = document.getElementById('chartValueByCommunity');
    if (ctxValComm && chartsData.value_by_community) {
        new Chart(ctxValComm, {
            type: 'bar',
            data: {
                labels: chartsData.value_by_community.map(c => c.community_name),
                datasets: [{
                    label: 'Approved Principal ($ USD)',
                    data: chartsData.value_by_community.map(c => c.total_principal),
                    backgroundColor: BORDEAUX,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: v => '$' + v } },
                    x: { ticks: { maxRotation: 25, minRotation: 0, font: { size: 10 } }, grid: { display: false } }
                }
            }
        });
    }

    // 4. Chart: Repayments Over Time
    const ctxRepayments = document.getElementById('chartRepaymentsOverTime');
    if (ctxRepayments && chartsData.repayments_over_time) {
        new Chart(ctxRepayments, {
            type: 'line',
            data: {
                labels: chartsData.repayments_over_time.map(r => r.p_date),
                datasets: [{
                    label: 'Repayments Amount ($ USD)',
                    data: chartsData.repayments_over_time.map(r => r.amount_total),
                    borderColor: ACCENT_EMERALD,
                    backgroundColor: 'rgba(5, 150, 105, 0.1)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2.5,
                    pointRadius: 4,
                    pointBackgroundColor: ACCENT_EMERALD
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: v => '$' + v } },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    // 5. Chart: Outstanding Balance by Community
    const ctxOutComm = document.getElementById('chartOutstandingByCommunity');
    if (ctxOutComm && chartsData.outstanding_by_community) {
        new Chart(ctxOutComm, {
            type: 'bar',
            data: {
                labels: chartsData.outstanding_by_community.map(c => c.name),
                datasets: [{
                    label: 'Outstanding ($ USD)',
                    data: chartsData.outstanding_by_community.map(c => c.outstanding),
                    backgroundColor: BORDEAUX_LIGHT,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: v => '$' + v } },
                    x: { ticks: { maxRotation: 25, minRotation: 0, font: { size: 10 } }, grid: { display: false } }
                }
            }
        });
    }

    // 6. Chart: Loan Due-Date Overview
    const ctxDue = document.getElementById('chartDueOverview');
    if (ctxDue && chartsData.due_overview) {
        new Chart(ctxDue, {
            type: 'doughnut',
            data: {
                labels: ['Not Yet Due', 'Due Soon (<= 3d)', 'Overdue', 'Fully Repaid'],
                datasets: [{
                    data: [
                        chartsData.due_overview.not_due,
                        chartsData.due_overview.due_soon,
                        chartsData.due_overview.overdue,
                        chartsData.due_overview.repaid
                    ],
                    backgroundColor: [SILVER, ACCENT_AMBER, ACCENT_ROSE, ACCENT_EMERALD],
                    borderWidth: 2,
                    borderColor: '#FFFFFF'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
                },
                cutout: '60%'
            }
        });
    }

    // 7. Chart: Membership Growth Over Time
    const ctxGrowth = document.getElementById('chartMemberGrowth');
    if (ctxGrowth && chartsData.member_growth) {
        new Chart(ctxGrowth, {
            type: 'line',
            data: {
                labels: chartsData.member_growth.map(m => m.date),
                datasets: [{
                    label: 'Cumulative Members',
                    data: chartsData.member_growth.map(m => m.total),
                    borderColor: BORDEAUX,
                    backgroundColor: 'rgba(80, 34, 45, 0.08)',
                    fill: true,
                    tension: 0.2,
                    borderWidth: 2,
                    pointRadius: 4,
                    pointBackgroundColor: BORDEAUX
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } },
                    x: { grid: { display: false } }
                }
            }
        });
    }
}

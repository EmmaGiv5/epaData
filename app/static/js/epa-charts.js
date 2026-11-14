// Shared chart functions for epaData

let epaCharts = {};

/**
 * Generate or replace a Chart.js graph.
 */
epaCharts.createChart = function (canvasId, chartType, labels, datasets, title) {

    const canvas = document.getElementById(canvasId);

    if (!canvas) {
        console.error("Chart canvas not found:", canvasId);
        return null;
    }

    // Destroy an existing chart before creating another.
    const existingChart = Chart.getChart(canvas);

    if (existingChart) {
        existingChart.destroy();
    }

    return new Chart(canvas, {
        type: chartType,

        data: {
            labels: labels,
            datasets: datasets
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,

            plugins: {
                legend: {
                    display: true
                },

                title: {
                    display: true,
                    text: title
                }
            },

            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
};


/**
 * Calculate basic descriptive statistics.
 */
epaCharts.calculateStatistics = function (values) {

    const numbers = values
        .map(Number)
        .filter(value => Number.isFinite(value));

    if (numbers.length === 0) {
        return null;
    }

    const sorted = [...numbers].sort((a, b) => a - b);

    const sum = numbers.reduce((total, value) => total + value, 0);

    const mean = sum / numbers.length;

    const median = sorted.length % 2 === 0
        ? (sorted[sorted.length / 2 - 1] +
           sorted[sorted.length / 2]) / 2
        : sorted[Math.floor(sorted.length / 2)];

    const variance = numbers.reduce(
        (total, value) => total + Math.pow(value - mean, 2),
        0
    ) / numbers.length;

    return {
        count: numbers.length,
        mean: mean,
        median: median,
        minimum: sorted[0],
        maximum: sorted[sorted.length - 1],
        standardDeviation: Math.sqrt(variance)
    };
};


/**
 * Display descriptive statistics in HTML.
 */
epaCharts.displayStatistics = function (containerId, statistics) {

    const container = document.getElementById(containerId);

    if (!container || !statistics) {
        return;
    }

    container.innerHTML = `
        <h3>Descriptive Results</h3>

        <table class="table">
            <tr><th>Number of Records</th><td>${statistics.count}</td></tr>
            <tr><th>Mean</th><td>${statistics.mean.toLocaleString()}</td></tr>
            <tr><th>Median</th><td>${statistics.median.toLocaleString()}</td></tr>
            <tr><th>Minimum</th><td>${statistics.minimum.toLocaleString()}</td></tr>
            <tr><th>Maximum</th><td>${statistics.maximum.toLocaleString()}</td></tr>
            <tr><th>Standard Deviation</th><td>${statistics.standardDeviation.toLocaleString()}</td></tr>
        </table>
    `;
};
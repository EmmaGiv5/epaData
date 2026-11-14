document.addEventListener("DOMContentLoaded", function () {

    // ==========================================
    // ELEMENTS
    // ==========================================

    const startYear = document.getElementById("startYear");
    const endYear = document.getElementById("endYear");

    const stateFilter = document.getElementById("stateFilter");
    const facilityFilter = document.getElementById("facilityFilter");

    const chartType = document.getElementById("chartType");
    const groupBy = document.getElementById("groupBy");

    const generateButton = document.getElementById("generateChart");

    const chartMessage = document.getElementById("chartMessage");
    const comparisonResults = document.getElementById("comparisonResults");

    const chartCanvas = document.getElementById("comparisonChart");

    let comparisonChart = null;
    let sensitivityChart = null;


    // ==========================================
    // VALIDATE PAGE
    // ==========================================

    if (!generateButton || !chartCanvas) {
        console.error("Comparison page elements are missing.");
        return;
    }

    if (typeof Chart === "undefined") {
        chartMessage.textContent = "Chart.js failed to load.";
        return;
    }


    // ==========================================
    // CONSTANTS
    // ==========================================

    const allowedStates = ["KY", "TN", "GA", "AL", "MS"];

    const metricNames = {
        co2_mass: "CO2 Emissions",
        so2_mass: "SO2 Emissions",
        nox_mass: "NOx Emissions",
        gross_load: "Gross Load",
        heat_input: "Heat Input",
        operating_time: "Operating Time"
    };

    const colors = [
        "#2563eb",
        "#dc2626",
        "#16a34a",
        "#9333ea",
        "#ea580c",
        "#0891b2"
    ];


    // ==========================================
    // GET SELECTED FILTERS
    // ==========================================

    function getFilters() {

        const selectedMetrics = Array.from(
            document.querySelectorAll(".metric-option:checked")
        ).map(input => input.value);

        return {

            start_year: Number(startYear.value),

            end_year: Number(endYear.value),

            state: stateFilter.value,

            facility: facilityFilter.value,

            group_by: groupBy.value,

            chart_type: chartType.value,

            metrics: selectedMetrics

        };

    }


    // ==========================================
    // GENERATE COMPARISON
    // ==========================================

    generateButton.addEventListener("click", async function () {

        const filters = getFilters();

        if (filters.start_year > filters.end_year) {

            chartMessage.textContent =
                "Start year cannot exceed end year.";

            return;

        }

        if (
            filters.start_year < 2015 ||
            filters.end_year > 2025
        ) {

            chartMessage.textContent =
                "Please select years between 2015 and 2025.";

            return;

        }

        if (!filters.metrics.length) {

            chartMessage.textContent =
                "Select at least one measurement.";

            return;

        }

        chartMessage.textContent = "Retrieving comparison data...";

        comparisonResults.innerHTML = "";

        const params = new URLSearchParams();

        params.set("start_year", filters.start_year);
        params.set("end_year", filters.end_year);

        params.set("state", filters.state);
        params.set("facility", filters.facility);

        params.set("group_by", filters.group_by);

        filters.metrics.forEach(metric => {
            params.append("metrics[]", metric);
        });

        try {

            const response = await fetch(
                `/api/comparison-data?${params.toString()}`
            );

            const data = await response.json();

            if (!response.ok) {

                throw new Error(
                    data.error || "Unable to retrieve comparison data."
                );

            }

            if (
                !data.labels ||
                !Array.isArray(data.labels) ||
                !data.datasets
            ) {

                throw new Error(
                    "The comparison API returned an unexpected response."
                );

            }

            if (!data.labels.length) {

                chartMessage.textContent =
                    "No records found for the selected filters.";

                destroyComparisonChart();

                return;

            }

            generateChart(data, filters);

            if (Array.isArray(data.records)) {
                generateTable(data.records);
            }

            chartMessage.textContent =
                "Comparison generated successfully.";

        } catch (error) {

            console.error("Comparison error:", error);

            chartMessage.textContent = error.message;

            destroyComparisonChart();

        }

    });


    // ==========================================
    // DESTROY EXISTING CHART SAFELY
    // ==========================================

    function destroyComparisonChart() {

        if (
            comparisonChart &&
            typeof comparisonChart.destroy === "function"
        ) {

            comparisonChart.destroy();

        }

        comparisonChart = null;

    }


    // ==========================================
    // GENERATE CHART
    // ==========================================

    function generateChart(data, filters) {

        destroyComparisonChart();

        const datasets = filters.metrics.map(
            (metric, index) => {

                const values = data.datasets[metric];

                if (!Array.isArray(values)) {

                    throw new Error(
                        `Missing dataset for ${metricNames[metric]}.`
                    );

                }

                return {

                    label: metricNames[metric] || metric,

                    data: values,

                    backgroundColor: colors[
                        index % colors.length
                    ],

                    borderColor: colors[
                        index % colors.length
                    ],

                    borderWidth: 2,

                    tension: 0.3,

                    fill: false

                };

            }
        );

        comparisonChart = new Chart(chartCanvas, {

            type: filters.chart_type,

            data: {

                labels: data.labels,

                datasets: datasets

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                interaction: {
                    intersect: false,
                    mode: "index"
                },

                plugins: {

                    title: {

                        display: true,

                        text: "EPA Measurement Comparisons"

                    },

                    legend: {

                        display: true,

                        position: "bottom"

                    }

                },

                scales: {

                    y: {

                        beginAtZero: true,

                        title: {

                            display: true,

                            text: "Measurement Values"

                        }

                    },

                    x: {

                        title: {

                            display: true,

                            text: `Grouped by ${filters.group_by}`

                        }

                    }

                }

            }

        });

    }


    // ==========================================
    // GENERATE RESULTS TABLE
    // ==========================================

    function generateTable(records) {

        comparisonResults.innerHTML = "";

        if (!records.length) {
            return;
        }

        const heading = document.createElement("h5");

        heading.textContent = "Comparison Data";

        comparisonResults.appendChild(heading);

        const table = document.createElement("table");

        table.className =
            "table table-striped table-bordered table-responsive";

        const fields = Object.keys(records[0]);

        const thead = document.createElement("thead");

        const headerRow = document.createElement("tr");

        fields.forEach(field => {

            const th = document.createElement("th");

            th.textContent = field.replaceAll("_", " ").toUpperCase();

            headerRow.appendChild(th);

        });

        thead.appendChild(headerRow);

        table.appendChild(thead);

        const tbody = document.createElement("tbody");

        records.forEach(record => {

            const row = document.createElement("tr");

            fields.forEach(field => {

                const cell = document.createElement("td");

                const value = record[field];

                cell.textContent =
                    typeof value === "number"
                        ? value.toLocaleString(
                            undefined,
                            { maximumFractionDigits: 2 }
                        )
                        : value ?? "";

                row.appendChild(cell);

            });

            tbody.appendChild(row);

        });

        table.appendChild(tbody);

        comparisonResults.appendChild(table);

    }


    // ==========================================
    // FILTER VALIDATION
    // ==========================================

    if (stateFilter) {

        stateFilter.addEventListener("change", function () {

            if (allowedStates.includes(stateFilter.value) ||
                stateFilter.value === "") {

                chartMessage.textContent = "";

            }

        });

    }


    // ==========================================
    // SENSITIVITY CHART CLEANUP
    // ==========================================

    function destroySensitivityChart() {

        if (
            sensitivityChart &&
            typeof sensitivityChart.destroy === "function"
        ) {

            sensitivityChart.destroy();

        }

        sensitivityChart = null;

    }


    // ==========================================
    // INITIALIZE
    // ==========================================

    console.log("EPA Comparisons JavaScript initialized.");

});
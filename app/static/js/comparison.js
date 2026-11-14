document.addEventListener("DOMContentLoaded", function () {

    const chartCanvas = document.getElementById("comparisonChart");
    const message = document.getElementById("chartMessage");
    const results = document.getElementById("comparisonResults");

    let comparisonChart = null;

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

    const generateButton = document.getElementById("generateChart");

    document.getElementById("applyFilters")
    ?.addEventListener("click", generateComparison);

    if (!chartCanvas || !generateButton) {
        console.error("Comparison chart elements were not found.");
        return;
    }

    generateButton.addEventListener("click", generateComparison);

    async function generateComparison() {

        const startYear = document.getElementById("startYear").value;
        const endYear = document.getElementById("endYear").value;

        const state = document.getElementById("stateFilter").value;
        const facility = document.getElementById("facilityFilter").value;

        const chartType = document.getElementById("chartType").value;
        const groupBy = document.getElementById("groupBy").value;

        const selectedMetrics = [
            ...document.querySelectorAll(".metric-option:checked")
        ].map(input => input.value);

        if (selectedMetrics.length === 0) {
            message.textContent = "Select at least one measurement.";
            return;
        }

        if (Number(startYear) > Number(endYear)) {
            message.textContent = "Start year cannot exceed end year.";
            return;
        }

        message.textContent = "Retrieving comparison data...";
        results.innerHTML = "";

        const params = new URLSearchParams();

        params.set("start_year", startYear);
        params.set("end_year", endYear);
        params.set("state", state);
        params.set("facility", facility);
        params.set("group_by", groupBy);

        selectedMetrics.forEach(metric => {
            params.append("metrics[]", metric);
        });

        try {

            const response = await fetch(
                `/api/comparison-data?${params.toString()}`
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Comparison failed.");
            }

            if (!data.labels || data.labels.length === 0) {
                message.textContent =
                    "No records were found for these filters.";

                if (
                    comparisonChart &&
                    typeof comparisonChart.destroy === "function"
                ) {
                    comparisonChart.destroy();
                }

                comparisonChart = null;

                return;
            }

            const datasets = selectedMetrics.map((metric, index) => {

                const color = colors[index % colors.length];

                return {
                    label: metricNames[metric],
                    data: data.datasets[metric],
                    borderColor: color,
                    backgroundColor: color,
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false
                };

            });

            if (comparisonChart) {
                comparisonChart.destroy();
            }

            comparisonChart = new Chart(chartCanvas, {

                type: chartType,

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
                            text: "EPA Measurement Comparison"
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
                                text: "Average Measurement Value"
                            }
                        },

                        x: {
                            title: {
                                display: true,
                                text: groupBy.charAt(0).toUpperCase()
                                    + groupBy.slice(1)
                            }
                        }

                    }

                }

            });

            message.textContent =
                "Comparison graph generated successfully.";

            generateResultsTable(data, selectedMetrics);

        } catch (error) {

            console.error("Comparison error:", error);

            message.textContent = error.message;

        }

    }

    function generateResultsTable(data, metrics) {

        const table = document.createElement("table");

        table.className = "table table-striped table-hover";

        const thead = document.createElement("thead");
        const header = document.createElement("tr");

        ["Comparison Group", ...metrics.map(
            metric => metricNames[metric]
        )].forEach(label => {

            const th = document.createElement("th");
            th.textContent = label;
            header.appendChild(th);

        });

        thead.appendChild(header);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");

        data.labels.forEach((label, index) => {

            const row = document.createElement("tr");

            const groupCell = document.createElement("td");
            groupCell.textContent = label;
            row.appendChild(groupCell);

            metrics.forEach(metric => {

                const cell = document.createElement("td");

                const value = data.datasets[metric][index];

                cell.textContent = value == null
                    ? "—"
                    : Number(value).toLocaleString(
                        undefined,
                        { maximumFractionDigits: 2 }
                    );

                row.appendChild(cell);

            });

            tbody.appendChild(row);

        });

        table.appendChild(tbody);
        results.replaceChildren(table);

    }

});
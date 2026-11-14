document.addEventListener("DOMContentLoaded", function() {

    const dataElement = document.getElementById("factoredData");

    if (!dataElement) return;

    const results = JSON.parse(dataElement.textContent);

    const categorySelect = document.getElementById("factoredCategory");
    const chartSelect = document.getElementById("factoredChartType");

    function updateFactoredGraph() {

        const category = categorySelect.value;
        const chartType = chartSelect.value;

        const filtered = results.filter(result =>
            category === "all" || result.category === category
        );

        // Group results by state, year, and category.
        const grouped = {};

        filtered.forEach(result => {

            const label = `${result.state} - ${result.year}`;

            grouped[label] = (grouped[label] || 0) + Number(result.value);

        });

        const labels = Object.keys(grouped);
        const values = Object.values(grouped);

        if (!labels.length) return;

        EPACharts.generate("factoredChart", {
            title: "TRACI Environmental Impact",
            labels: labels,
            datasets: [{
                label: category === "all" ?
                    "Calculated Impact (mixed categories)" : category,
                data: values,
                backgroundColor: "#16a34a",
                borderColor: "#16a34a"
            }]
        }, chartType);

    }

    categorySelect.addEventListener("change", updateFactoredGraph);
    chartSelect.addEventListener("change", updateFactoredGraph);

    updateFactoredGraph();

});
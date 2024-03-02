const finalReportQuery = `
    query {
        final_report(run_id: "${run_id}") {
            data
        }
    }
`;
console.log(finalReportQuery);

fetch("/graphql", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
    },
    body: JSON.stringify({ query: finalReportQuery }),
})
    .then((response) => response.json())
    .then((obj) => {
        console.log(obj);

        const finalReport = obj.data.final_report;
        const finalReportSection =
            document.getElementById("finalReportSection");

        if (!obj.data || obj.data.final_report === null) {
            console.log(`Final report not found for run_id '${run_id}'`);
            finalReportSection.innerHTML = "<div>No final report found!</div>";
        } else {
            const finalReportObject = JSON5.parse(finalReport["data"]);
            var formattedFinalReport = "";
            for (var key in finalReportObject) {
                formattedFinalReport += `<div class="mb-4 break-words"><strong>${key}:</strong> ${finalReportObject[key]}</div>`;
            }
            finalReportSection.innerHTML = formattedFinalReport;
        }
    })
    .catch((error) => {
        console.error("Error fetching final_report:", error);
    });

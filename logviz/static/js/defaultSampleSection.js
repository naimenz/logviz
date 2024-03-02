const pageQuery = `
    query {
        sample_page(run_id: "${run_id}", page_id: ${page_id}) {
            run_id
            sample_id
            sample_metrics {
                data
            }
            sampling_events {
                event_id
                data {
                    prompt {
                        role
                        content
                        name
                    }
                    sampled
                }
            }
        }
        metadata(run_id: "${run_id}") {
            num_samples
        }
    }

`;
        // spec(run_id: "${run_id}") {
        //     num_samples
        // }
    // }

fetch("/graphql", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
    },
    body: JSON.stringify({ query: pageQuery }),
})
    .then((response) => response.json())
    .then((obj) => {
        console.log(obj);

        if (!obj.data || obj.data.sample_page === null) {
            return console.error(
                `Page not found for run_id '${run_id}' and page_id '${page_id}'`
            );
        }
        const metrics = obj.data.sample_page.sample_metrics;
        const samplingEvents = obj.data.sample_page.sampling_events;
        const numSamples = obj.data.metadata.num_samples;

        activateButtons(numSamples, page_id);
        populateMetrics(metrics);
        buildTables(samplingEvents);
    });

    function activateButtons(numSamples, page_id) {
        // TODO (ian): use proper tailwind installation to
        // have 'disabled' styling work better
        const prevButton = document.getElementById("prev-button");
        const nextButton = document.getElementById("next-button");
        console.log(`numSamples: ${numSamples}, page_id: ${page_id}`);
        if (parseInt(page_id) === 1) {
            prevButton.classList = "px-4 py-2 text-white rounded bg-gray-200 text-slate-500 border-slate-200"
            prevButton.disabled = true;
        }
        if (parseInt(page_id) === parseInt(numSamples)) {
            nextButton.classList = "px-4 py-2 text-white rounded bg-gray-200 text-slate-500 border-slate-200"
            nextButton.disabled = true;
        }
        // change text of page-number div to reflect current page
        const pageNumber = document.getElementById("page-number");
        pageNumber.innerHTML = `Page ${parseInt(page_id)} of ${numSamples}`;
    }

function populateMetrics(metrics) {
    const metricsSection = document.getElementById("metrics-section");
    metricsSection.innerHTML = metrics;
    if (metrics === null) {
        metricsSection.innerHTML = "No metrics found for this page!";
        return;
    }
    const metricsObject = JSON5.parse(metrics["data"]);
    var formattedMetrics = "";
    for (var key in metricsObject) {
        formattedMetrics += `<div class="mb-4 break-words"><strong>${key}:</strong> ${JSON5.stringify(metricsObject[key])}</div>`;
    }
    metricsSection.innerHTML = formattedMetrics;
}

function buildTables(samples) {
    samples.forEach((event, eventIndex) => {
        const tbl = generateTable(event, eventIndex);
        // appends <table> into #sample-section
        document.getElementById("sample-section").appendChild(tbl);
    });
    document.querySelectorAll(".caption").forEach((caption) => {
        caption.nextElementSibling.style.display = "none";
        caption.addEventListener("click", toggleTableBody);
    });
}

function generateTable(event, eventIndex) {
    const containerDiv = document.createElement("div");
    containerDiv.className = "my-4 border-2 rounded-md border-black";
    const captionDiv = document.createElement("div");
    captionDiv.className =
        "caption text-lg font-semibold p-4 bg-white text-left cursor-pointer rounded-md border-b-2 border-black";
    const captionText = document.createTextNode(`Event ID: ${event.event_id}`);
    captionDiv.appendChild(captionText);
    containerDiv.appendChild(captionDiv);

    const tbl = document.createElement("table");
    tbl.className =
        // "min-w-full table-auto border-collapse border border-gray-900";
        "min-w-full table-auto border-separate border-black";

    const tblBody = document.createElement("tbody");
    tblBody.className = "transition-all duration-500";

    // add header with Role and Content
    const thead = createTableHeader();
    tbl.appendChild(thead);

    // add data rows
    event.data.prompt.forEach((prompt, promptIndex) => {
        const rowClass =
            (eventIndex + promptIndex) % 2 === 0 ? "bg-gray-100" : "bg-white";
        const row = createTableRow(prompt.role, prompt.content);
        row.classList.add(rowClass);
        tblBody.appendChild(row);
    });

    // add sampled row
    const sampledRow = createSampledRow(event.data.sampled);
    tblBody.appendChild(sampledRow);
    tbl.appendChild(tblBody);
    containerDiv.appendChild(tbl);
    return containerDiv;
}

function createTableHeader() {
    const thead = document.createElement("thead");
    const theadRow = document.createElement("tr");
    theadRow.className = "bg-gray-300";

    const roleHeader = document.createElement("th");
    roleHeader.className = "px-4 py-2 text-gray-600";
    // "border border-gray-300 px-4 py-2 text-gray-600";
    const roleHeaderText = document.createTextNode("Role");
    roleHeader.appendChild(roleHeaderText);
    theadRow.appendChild(roleHeader);

    const contentHeader = document.createElement("th");
    contentHeader.className = "px-4 py-2 text-gray-600";
    // "border border-gray-300 px-4 py-2 text-gray-600";
    const contentHeaderText = document.createTextNode("Content");
    contentHeader.appendChild(contentHeaderText);
    theadRow.appendChild(contentHeader);

    thead.appendChild(theadRow);
    return thead;
}

function createTableRow(role, content) {
    const row = document.createElement("tr");

    const roleCell = document.createElement("td");
    // roleCell.className = "border border-gray-300 px-4 py-2";
    roleCell.className = "px-4 py-2";
    const roleCellText = document.createTextNode(role);
    roleCell.appendChild(roleCellText);
    row.appendChild(roleCell);

    const contentCell = document.createElement("td");
    // contentCell.className = "border border-gray-300 px-4 py-2";
    contentCell.className = "px-4 py-2";
    contentCell.style["white-space"] = "pre-wrap";
    const contentCellText = document.createTextNode(content);
    contentCell.appendChild(contentCellText);
    row.appendChild(contentCell);

    return row;
}

function createSampledRow(sampled) {
    const row = document.createElement("tr");
    row.className = "bg-blue-200";
    const roleCell = document.createElement("td");
    // roleCell.className = "border border-gray-300 px-4 py-2";
    roleCell.className = "px-4 py-2";
    const roleCellText = document.createTextNode("Sampled");
    roleCell.appendChild(roleCellText);
    row.appendChild(roleCell);

    const sampledCell = document.createElement("td");
    // sampledCell.className = "border border-gray-300 px-4 py-2";
    sampledCell.className = "px-4 py-2";
    sampledCell.style["white-space"] = "pre-wrap";
    const sampledCellText = document.createTextNode(sampled);
    sampledCell.appendChild(sampledCellText);

    row.appendChild(sampledCell);
    return row;
}

function toggleTableBody(event) {
    const tableBody = event.currentTarget.nextElementSibling;
    if (tableBody.style.display === "none") {
        tableBody.style.display = "";
    } else {
        tableBody.style.display = "none";
    }
}

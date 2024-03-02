const specQuery = `
    query {
        spec(run_id: "${run_id}") {
            completion_fns
            base_eval
            split
            created_at
        }
    }
`;


fetch("/graphql", {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
    },
    body: JSON.stringify({ query: specQuery }),
})
    .then((response) => response.json())
    .then((obj) => {
        console.log(obj);

        if (!obj.data || obj.data.spec === null) {
            return console.error(`Spec not found for run_id '${run_id}'`);
        }

        const spec = obj.data.spec;

        const specSection = document.getElementById("specSection");

        specSection.innerHTML = `
            <div class="mb-2"><strong>Run ID:</strong> ${run_id}</div>
            <div class="mb-2"><strong>Solvers:</strong> ${spec.completion_fns.join(
                ", "
            )}</div>
            <div class="mb-2"><strong>Eval:</strong> ${spec.base_eval}</div>
            <div class="mb-2"><strong>Split:</strong> ${spec.split}</div>
            <div class="mb-2"><strong>Created at:</strong> ${spec.created_at} </div>
        `;
    })
    .catch((error) => {
        console.error("Error fetching spec:", error);
    });

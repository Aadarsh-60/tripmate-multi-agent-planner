let currentThreadId = localStorage.getItem("travel_thread_id") || null;
let currentDraft = null; // Store HITL draft

function setPrompt(text) {
    document.getElementById("userInput").value = text;
}

function setLoading(isLoading, text = "Generating Plan") {
    const sendBtn = document.getElementById("sendBtn");
    const btnText = document.getElementById("btnText");
    const btnLoader = document.getElementById("btnLoader");

    sendBtn.disabled = isLoading;

    if (isLoading) {
        btnText.textContent = text;
        btnLoader.classList.remove("hidden");
    } else {
        btnText.textContent = "Generate Plan";
        btnLoader.classList.add("hidden");
    }
}

function showError(message) {
    const errorBox = document.getElementById("errorBox");
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

function hideError() {
    const errorBox = document.getElementById("errorBox");
    errorBox.classList.add("hidden");
    errorBox.textContent = "";
}

function renderPlan(plan) {
    const resultBox = document.getElementById("resultBox");
    
    let html = `<div class="plan-summary">
        <h3>Summary</h3>
        <p>${plan.trip_summary}</p>
        <p><strong>Budget:</strong> ${plan.estimated_budget}</p>
        <p><strong>Weather:</strong> ${plan.weather_info}</p>
        <p><strong>Currency:</strong> ${plan.exchange_rates}</p>
    </div>`;

    html += `<h3>Flights</h3><ul>`;
    plan.flights.forEach(f => {
        html += `<li>${f.airline} (${f.flight_number}) - ${f.departure} to ${f.arrival} [${f.status}]</li>`;
    });
    html += `</ul>`;

    html += `<h3>Recommended Places</h3><ul>`;
    plan.hotels_and_places.forEach(p => {
        html += `<li>${p}</li>`;
    });
    html += `</ul>`;

    html += `<h3>Itinerary</h3><div class="itinerary">`;
    plan.itinerary.forEach(day => {
        html += `<div class="day-card">
            <h4>Day ${day.day}: ${day.title}</h4>
            <ul>`;
        day.activities.forEach(act => {
            html += `<li>${act}</li>`;
        });
        html += `</ul></div>`;
    });
    html += `</div>`;

    resultBox.innerHTML = html;
    document.getElementById("resultSection").classList.remove("hidden");
}

function showHITL(draft, thread_id) {
    const resultBox = document.getElementById("resultBox");
    let html = `
        <div class="hitl-box">
            <h3>Review Gathered Information</h3>
            <p>The AI has gathered data. Do you want to proceed and generate the final itinerary?</p>
            <textarea id="feedbackInput" placeholder="Add feedback to change the plan or leave empty to approve..."></textarea>
            <br>
            <button onclick="approveHITL('${thread_id}')">Approve & Continue</button>
        </div>
    `;
    resultBox.innerHTML = html;
    document.getElementById("resultSection").classList.remove("hidden");
}

async function approveHITL(thread_id) {
    const feedback = document.getElementById("feedbackInput").value;
    setLoading(true, "Finalizing...");
    
    try {
        const response = await fetch("/api/approve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                thread_id: thread_id,
                action: "approve",
                feedback: feedback
            })
        });
        
        await handleSSEStream(response);
    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

async function handleSSEStream(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let done = false;
    
    const resultBox = document.getElementById("resultBox");
    document.getElementById("resultSection").classList.remove("hidden");

    while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
            const chunk = decoder.decode(value);
            const lines = chunk.split("\n\n");
            
            for (let line of lines) {
                if (line.startsWith("data: ")) {
                    const data = JSON.parse(line.replace("data: ", ""));
                    
                    if (data.type === "progress") {
                        resultBox.innerHTML = `<p>Agent <strong>${data.node}</strong> is working...</p>`;
                    } else if (data.type === "hitl_wait") {
                        showHITL(data.draft, data.thread_id);
                        return; // Wait for user interaction
                    } else if (data.type === "final_plan") {
                        renderPlan(data.plan);
                    } else if (data.type === "error") {
                        showError(data.error);
                    }
                }
            }
        }
    }
}

async function sendMessage() {
    hideError();
    const input = document.getElementById("userInput");
    const message = input.value.trim();

    if (!message) {
        showError("Please enter your travel request first.");
        return;
    }

    setLoading(true, "Thinking...");
    document.getElementById("resultBox").innerHTML = "<p>Starting...</p>";

    try {
        const response = await fetch("/api/travel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                thread_id: currentThreadId
            })
        });

        // Parse SSE Stream
        await handleSSEStream(response);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

function downloadPDF() {
    // Basic PDF download (can be improved)
    window.print();
}
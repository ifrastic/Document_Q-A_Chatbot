const documentSelect = document.getElementById("documentSelect");
const chatForm = document.getElementById("chatForm");
const questionInput = document.getElementById("questionInput");
const chatMessage = document.getElementById("chatMessage");
const newChatButton = document.getElementById("newChat");

// Load documents into the dropdown
async function loadDocuments() {
    try {
        const response = await fetch("/api/documents");
        if (!response.ok) throw new Error("Could not load documents.");

        const result = await response.json();
        const documents = result.documents || [];

        const previousSelection = documentSelect.value;
        documentSelect.replaceChildren();

        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Select a document";
        documentSelect.appendChild(placeholder);

        for (const doc of documents) {
            const option = document.createElement("option");
            option.value = doc.id;
            option.textContent = doc.filename;
            documentSelect.appendChild(option);
        }

        if (documents.some(doc => doc.id === previousSelection)) {
            documentSelect.value = previousSelection;
        }
    } catch (error) {
        console.error("Document loading error:", error);
    }
}

// Send feedback to the server
async function sendFeedback(documentId, question, answer, rating, comment) {
    const response = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            document_id: documentId,
            question: question,
            answer: answer,
            rating: rating,
            comment: comment
        })
    });

    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.detail || "Could not save feedback.");
    }
}

// Add the like / dislike buttons under a bot answer
function addFeedbackButtons(documentId, question, answer) {
    const box = document.createElement("div");
    box.className = "feedback-box";

    const row = document.createElement("div");
    row.className = "feedback-row";

    const label = document.createElement("span");
    label.textContent = "Was this helpful?";

    const likeButton = document.createElement("button");
    likeButton.type = "button";
    likeButton.className = "feedback-btn";
    likeButton.textContent = "👍";
    likeButton.title = "Good answer";

    const dislikeButton = document.createElement("button");
    dislikeButton.type = "button";
    dislikeButton.className = "feedback-btn";
    dislikeButton.textContent = "👎";
    dislikeButton.title = "Needs improvement";

    const status = document.createElement("span");
    status.className = "feedback-status";

    row.append(label, likeButton, dislikeButton, status);
    box.appendChild(row);

    function finish(message) {
        likeButton.disabled = true;
        dislikeButton.disabled = true;
        status.textContent = message;
    }

    // 👍 is sent immediately
    likeButton.addEventListener("click", async () => {
        likeButton.disabled = true;
        dislikeButton.disabled = true;
        try {
            await sendFeedback(documentId, question, answer, 1, "");
            finish("Thanks for your feedback!");
        } catch (error) {
            likeButton.disabled = false;
            dislikeButton.disabled = false;
            status.textContent = `Error: ${error.message}`;
        }
    });

    // 👎 opens a small box to say what to improve
    dislikeButton.addEventListener("click", () => {
        if (box.querySelector(".feedback-form")) return;

        likeButton.disabled = true;
        dislikeButton.disabled = true;

        const form = document.createElement("div");
        form.className = "feedback-form";

        const comment = document.createElement("textarea");
        comment.rows = 2;
        comment.placeholder = "What could be improved? (optional)";

        const submit = document.createElement("button");
        submit.type = "button";
        submit.textContent = "Send";

        form.append(comment, submit);
        box.appendChild(form);

        submit.addEventListener("click", async () => {
            submit.disabled = true;
            try {
                await sendFeedback(documentId, question, answer, -1, comment.value);
                form.remove();
                finish("Thanks, we will use this to improve.");
            } catch (error) {
                submit.disabled = false;
                status.textContent = `Error: ${error.message}`;
            }
        });
    });

    chatMessage.appendChild(box);
}

// Start a fresh chat without deleting uploaded documents
newChatButton.addEventListener("click", () => {
    chatMessage.replaceChildren();

    const welcome = document.createElement("div");
    welcome.className = "welcome-message";

    const heading = document.createElement("h3");
    heading.textContent = "How can I help you?";

    const paragraph = document.createElement("p");
    paragraph.textContent = "Select one document and ask a question about it.";

    welcome.append(heading, paragraph);
    chatMessage.appendChild(welcome);

    questionInput.value = "";
    questionInput.focus();
});

// Ask a question about the selected document
chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = questionInput.value.trim();
    const selectedDocumentId = documentSelect.value;

    if (!question) return;

    if (!selectedDocumentId) {
        const warning = document.createElement("p");
        warning.textContent = "Please select one document first.";
        chatMessage.appendChild(warning);
        return;
    }

    const userMessage = document.createElement("p");
    userMessage.textContent = `You: ${question}`;
    chatMessage.appendChild(userMessage);

    questionInput.value = "";

    const loadingMessage = document.createElement("p");
    loadingMessage.textContent = "Bot: typing...";
    chatMessage.appendChild(loadingMessage);

    const sendButton = chatForm.querySelector('button[type="submit"]');
    if (sendButton) sendButton.disabled = true;

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                selected_document_ids: [selectedDocumentId]
            })
        });

        const result = await response.json();
        loadingMessage.remove();

        if (!response.ok) {
            throw new Error(result.detail || "Chat request failed.");
        }

        const botMessage = document.createElement("p");
        botMessage.appendChild(document.createTextNode("Bot: "));

        // **text** becomes bold
        const parts = result.answer.split("**");
        parts.forEach((part, index) => {
            if (index % 2 === 1) {
                const boldText = document.createElement("strong");
                boldText.textContent = part;
                botMessage.appendChild(boldText);
            } else {
                botMessage.appendChild(document.createTextNode(part));
            }
        });

        chatMessage.appendChild(botMessage);

        // NEW: like / dislike buttons under the answer
        addFeedbackButtons(selectedDocumentId, question, result.answer);

        chatMessage.scrollTop = chatMessage.scrollHeight;

    } catch (error) {
        loadingMessage.textContent = `Error: ${error.message}`;
    } finally {
        if (sendButton) sendButton.disabled = false;
    }
});

loadDocuments();
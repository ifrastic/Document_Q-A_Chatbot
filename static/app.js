const fileInput = document.getElementById("fileInput");
const selectedFiles = document.getElementById("selectedFiles");
const uploadButton = document.getElementById("uploadButton");
const uploadStatus = document.getElementById("uploadStatus");
const documentTable = document.getElementById("documentTable");
const documentCount = document.getElementById("documentCount");

function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Show the list of uploaded documents
async function loadDocuments() {
    try {
        const response = await fetch("/api/documents");
        if (!response.ok) throw new Error("Could not load documents.");

        const result = await response.json();
        const documents = result.documents || [];

        documentCount.textContent =
            `${documents.length} document${documents.length === 1 ? "" : "s"} uploaded`;

        documentTable.replaceChildren();

        if (documents.length === 0) {
            const item = document.createElement("li");
            item.textContent = "No documents uploaded yet.";
            documentTable.appendChild(item);
            return;
        }

        for (const doc of documents) {
            const item = document.createElement("li");

            const name = document.createElement("strong");
            name.textContent = doc.filename;

            const meta = document.createElement("span");
            meta.className = "doc-meta";
            meta.textContent = formatSize(doc.size_bytes);

            item.append(name);
            documentTable.appendChild(item);
        }
    } catch (error) {
        console.error("Document loading error:", error);
        documentTable.textContent = "Could not load documents: " + error.message;
    }
}

// Show files chosen for upload
fileInput.addEventListener("change", () => {
    selectedFiles.replaceChildren();

    for (const file of fileInput.files) {
        const item = document.createElement("p");
        item.textContent = `${file.name} (${formatSize(file.size)})`;
        selectedFiles.appendChild(item);
    }
});

// Upload documents
uploadButton.addEventListener("click", async () => {
    if (fileInput.files.length === 0) {
        uploadStatus.textContent = "Please select a file first.";
        return;
    }

    const formData = new FormData();
    for (const file of fileInput.files) {
        formData.append("files", file);
    }

    uploadButton.disabled = true;
    uploadStatus.textContent = "Uploading documents...";

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Upload failed.");
        }

        uploadStatus.textContent = result.message;
        fileInput.value = "";
        selectedFiles.replaceChildren();

        await loadDocuments();

    } catch (error) {
        uploadStatus.textContent = `Error: ${error.message}`;
    } finally {
        uploadButton.disabled = false;
    }
});

loadDocuments();
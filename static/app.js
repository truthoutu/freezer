document.addEventListener("DOMContentLoaded", () => {
    const searchForm = document.getElementById("searchForm");
    const searchBtn = document.getElementById("searchBtn");
    const btnText = searchBtn.querySelector(".btn-text");
    const contactsTbody = document.getElementById("contactsTbody");
    const resultsStats = document.getElementById("resultsStats");
    const exportExcelBtn = document.getElementById("exportExcelBtn");
    const exportCsvBtn = document.getElementById("exportCsvBtn");
    const toast = document.getElementById("toast");

    let currentSessionId = null;

    searchForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const country = document.getElementById("country").value;
        const occupation = document.getElementById("occupation").value;
        const gender = document.getElementById("gender").value;
        const limit = parseInt(document.getElementById("limit").value, 10) || 20;
        const customUrlsText = document.getElementById("customUrls").value.trim();
        const customUrls = customUrlsText ? customUrlsText.split('\n').map(url => url.trim()).filter(url => url) : [];

        searchBtn.disabled = true;
        btnText.textContent = "[LIGHTNING] Crawling & Harvesting...";
        resultsStats.textContent = customUrls.length > 0 
            ? `Scraping ${customUrls.length} custom URLs with Firecrawl...`
            : `Automated intelligence engine scanning for ${gender || "all"} ${occupation}s in ${country}...`;
        contactsTbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="7">
                    <div style="display:flex; flex-direction:column; align-items:center; gap:0.75rem; padding: 2.5rem;">
                        <span class="spinner"></span>
                        <div>${customUrls.length > 0 ? 'Scraping custom URLs with Firecrawl...' : 'Crawling & extracting contacts...'} Please wait a few moments.</div>
                    </div>
                </td>
            </tr>
        `;

        try {
            const response = await fetch("/api/harvest", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    country,
                    occupation,
                    gender,
                    limit,
                    custom_urls: customUrls
                })
            });

            const data = await response.json();

            if (data.success) {
                currentSessionId = data.session_id;
                renderContacts(data.records);
                resultsStats.textContent = `Successfully harvested ${data.count} contact targets.`;
                if (data.count > 0) {
                    exportExcelBtn.disabled = false;
                    exportCsvBtn.disabled = false;
                } else {
                    exportExcelBtn.disabled = true;
                    exportCsvBtn.disabled = true;
                }
            } else {
                resultsStats.textContent = `Error: ${data.error || "Failed to harvest contacts."}`;
                contactsTbody.innerHTML = `<tr class="empty-row"><td colspan="7">Error harvesting contacts: ${escapeHtml(data.error || "")}</td></tr>`;
            }
        } catch (err) {
            resultsStats.textContent = `Network Error: ${err.message}`;
            contactsTbody.innerHTML = `<tr class="empty-row"><td colspan="7">Connection failed. Check server status.</td></tr>`;
        } finally {
            searchBtn.disabled = false;
            btnText.textContent = `[LIGHTNING] Start Harvesting ${limit} Targets`;
        }
    });

    function renderContacts(records) {
        if (!records || records.length === 0) {
            contactsTbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="7">No contacts matched your criteria. Try selecting 'Any Gender' or adjusting the occupation keyword.</td>
                </tr>
            `;
            return;
        }

        contactsTbody.innerHTML = records.map((c, index) => {
            const name = c["Name"] || "N/A";
            const occ = c["Occupation"] || "N/A";
            const gender = c["Gender (Inferred)"] || "Unknown";
            const phone = c["Phone Number"] || "N/A";
            const country = c["Country"] || "Unknown";

            return `
                <tr>
                    <td><strong>${index + 1}</strong></td>
                    <td>${escapeHtml(name)}</td>
                    <td><span class="badge">${escapeHtml(occ)}</span></td>
                    <td>${escapeHtml(gender)}</td>
                    <td><strong style="color: #34d399;">${escapeHtml(phone)}</strong></td>
                    <td>${escapeHtml(country)}</td>
                    <td>
                        <button class="btn-copy" onclick="copyPhone('${escapeHtml(phone)}')">Copy</button>
                    </td>
                </tr>
            `;
        }).join("");
    }

    exportExcelBtn.addEventListener("click", () => {
        const url = currentSessionId ? `/api/export/excel/${currentSessionId}` : "/api/export/excel";
        window.location.href = url;
    });

    exportCsvBtn.addEventListener("click", () => {
        const url = currentSessionId ? `/api/export/csv/${currentSessionId}` : "/api/export/csv";
        window.location.href = url;
    });

    window.copyPhone = function(phone) {
        if (!phone || phone === "N/A") return;
        navigator.clipboard.writeText(phone).then(() => {
            showToast(`Copied ${phone} to clipboard!`);
        });
    };

    function showToast(msg) {
        toast.textContent = msg;
        toast.classList.remove("hidden");
        setTimeout(() => {
            toast.classList.add("hidden");
        }, 2500);
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }
});

const BASE = "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  getDigest: () => request("/api/digest"),
  getPostings: ({ status, actionable, limit = 100, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (status) params.set("status", status);
    if (actionable) params.set("actionable", "true");
    return request(`/api/postings?${params.toString()}`);
  },
  skipPosting: (id) => request(`/api/postings/${id}/skip`, { method: "POST" }),
  applyToPosting: (id) => request(`/api/postings/${id}/apply`, { method: "POST" }),
  getApplications: (status) => request(`/api/applications${status ? `?status=${status}` : ""}`),
  decideApplication: (id, decision) =>
    request(`/api/applications/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
  fillApplication: (id) => request(`/api/applications/${id}/fill`, { method: "POST" }),
  getTailoring: (id) => request(`/api/applications/${id}/tailoring`),
  reviseApplication: (id, instruction) =>
    request(`/api/applications/${id}/revise`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    }),
  submitApplication: (id, confirmed) =>
    request(`/api/applications/${id}/submit`, {
      method: "POST",
      body: JSON.stringify({ confirmed }),
    }),
  runDiscoverSearch: () => request("/api/actions/discover-search", { method: "POST" }),
  runDiscoverCompanies: () => request("/api/actions/discover-companies", { method: "POST" }),
  runDiscover: () => request("/api/actions/discover", { method: "POST" }),
  runFilterPostings: () => request("/api/actions/filter-postings", { method: "POST" }),
  runMatch: () => request("/api/actions/match", { method: "POST" }),
  runTailor: () => request("/api/actions/tailor", { method: "POST" }),
  prepareBatch: (count) =>
    request("/api/actions/prepare-batch", {
      method: "POST",
      body: JSON.stringify({ count }),
    }),
  fillBatch: (applicationIds) =>
    request("/api/actions/fill-batch", {
      method: "POST",
      body: JSON.stringify({ application_ids: applicationIds }),
    }),
  submitBatch: (applicationIds, confirmed) =>
    request("/api/actions/submit-batch", {
      method: "POST",
      body: JSON.stringify({ application_ids: applicationIds, confirmed }),
    }),
  getFilters: () => request("/api/filters"),
  setFilters: (filters) =>
    request("/api/filters", { method: "PUT", body: JSON.stringify(filters) }),
  getResume: () => request("/api/resume"),
  importResume: async (file) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/api/resume/import`, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Import failed: ${res.status}`);
    }
    return res.json();
  },
};

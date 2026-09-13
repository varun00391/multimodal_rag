const API = "/api";

export function getToken() {
  return localStorage.getItem("nexus_token");
}

export function setSession(token, user) {
  localStorage.setItem("nexus_token", token);
  localStorage.setItem("nexus_user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem("nexus_token");
  localStorage.removeItem("nexus_user");
}

export async function api(path, { method = "GET", body, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (!isForm) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    clearSession();
    if (!path.startsWith("/auth/login")) {
      window.location.href = "/login";
    }
    const err = new Error(data.detail || "Unauthorized");
    err.status = 401;
    throw err;
  }
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
    throw new Error(detail || "Request failed");
  }
  return data;
}

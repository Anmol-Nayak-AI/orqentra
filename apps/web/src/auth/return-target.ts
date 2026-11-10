// Same-tab navigation only. Invitation fragments never enter query strings or server logs.
const key = "orqentra.auth-return";
export function authReturnTarget(): string {
  try {
    const path = sessionStorage.getItem(key) ?? "/app";
    return /^\/app(?:\/|$|[?#])/.test(path) && !/[\\\r\n]/.test(path) ? path : "/app";
  } catch {
    return "/app";
  }
}
export function rememberAuthTarget(path: string) {
  try {
    if (/^\/app(?:\/|$|[?#])/.test(path) && !/[\\\r\n]/.test(path))
      sessionStorage.setItem(key, path);
  } catch {
    /* Navigation still falls back to the organization directory. */
  }
}
export function clearAuthTarget() {
  try {
    sessionStorage.removeItem(key);
  } catch {
    /* Storage may be unavailable. */
  }
}

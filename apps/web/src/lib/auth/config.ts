export const DEV_USER_ID =
  import.meta.env.DEV
    ? import.meta.env.VITE_DEV_USER_ID ?? "user_admin"
    : import.meta.env.VITE_DEV_USER_ID ?? "";

export function isDevSessionEnabled() {
  return Boolean(DEV_USER_ID);
}

export function isStrictAuthEnabled() {
  if (import.meta.env.VITE_REQUIRE_AUTH === "true") {
    return true;
  }
  return !isDevSessionEnabled();
}

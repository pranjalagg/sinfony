// Light is the default look; dark is opt-in and remembered.

export const THEME_KEY = "sinfony-theme";

/** "dark" only when the user chose it; anything else, or blocked storage, is "light". */
export function loadTheme(storage = globalThis.localStorage) {
  try {
    return storage?.getItem(THEME_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export const nextTheme = (theme) => (theme === "dark" ? "light" : "dark");

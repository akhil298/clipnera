/** Where the shell keeps the theme choice (`usePersistentState`, so the value is JSON). */
export const THEME_STORAGE_KEY = 'cn_theme';

/**
 * Runs before the shell hydrates, so a light-theme user never sees the dark
 * default flash (the shell's own effect takes over after mount). Mirrors
 * `useApplyTheme` in ShellContext: "system" follows the OS, anything unreadable is dark.
 */
export const THEME_BOOT_SCRIPT = `(function(){try{var t=JSON.parse(localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)}));if(t==='system')t=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';document.documentElement.dataset.theme=t==='light'?'light':'dark'}catch(e){document.documentElement.dataset.theme='dark'}})()`;

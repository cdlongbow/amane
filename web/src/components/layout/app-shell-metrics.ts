/** 与 `AppShell.Header` 同高; 填视口的页面用它算 Main 内容区. */
export const APP_SHELL_HEADER_HEIGHT = 60;

/** AppShell.Main 内容区高度 (扣除 header 与上下 `padding="md"`). */
export const APP_SHELL_MAIN_HEIGHT =
  `calc(100dvh - ${APP_SHELL_HEADER_HEIGHT}px - 2 * var(--mantine-spacing-md))` as const;

import { createRootRoute } from "@tanstack/react-router";
import { AppShellLayout } from "@/components/layout/app-shell";
import { ErrorBoundary } from "@/components/error-boundary";

export const Route = createRootRoute({ component: RootLayout });

function RootLayout() {
  return (
    <ErrorBoundary>
      <AppShellLayout />
    </ErrorBoundary>
  );
}

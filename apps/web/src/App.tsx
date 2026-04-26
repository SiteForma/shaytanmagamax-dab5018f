import { Suspense, lazy } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppShell } from "@/components/layout/AppShell";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { CapabilityGuard } from "@/components/auth/CapabilityGuard";
import { Skeleton } from "@/components/ui-ext/Skeleton";
import { createQueryClient } from "@/lib/query/client";
import { ThemeProvider } from "@/lib/theme";

const Index = lazy(() => import("./pages/Index.tsx"));
const NotFound = lazy(() => import("./pages/NotFound.tsx"));
const LoginPage = lazy(() => import("@/features/auth/LoginPage"));
const ReservePage = lazy(() => import("@/features/reserve/ReservePage"));
const SkuExplorerPage = lazy(() => import("@/features/sku/SkuExplorerPage"));
const ClientsPage = lazy(() => import("@/features/clients/ClientsPage"));
const StockPage = lazy(() => import("@/features/stock/StockPage"));
const InboundPage = lazy(() => import("@/features/inbound/InboundPage"));
const UploadCenterPage = lazy(() => import("@/features/uploads/UploadCenterPage"));
const MappingPage = lazy(() => import("@/features/mapping/MappingPage"));
const QualityPage = lazy(() => import("@/features/quality/QualityPage"));
const AiConsolePage = lazy(() => import("@/features/assistant/AiConsolePage"));
const AdminPage = lazy(() => import("@/features/admin/AdminPage"));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage"));

const queryClient = createQueryClient();

function RouteFallback() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-24" />
      <Skeleton className="h-[520px]" />
    </div>
  );
}

function AppLayout() {
  return (
    <AuthGuard>
      <AppShell>
        <Suspense fallback={<RouteFallback />}>
          <Outlet />
        </Suspense>
      </AppShell>
    </AuthGuard>
  );
}

function GuardedRoute({
  capability,
  children,
}: {
  capability: Parameters<typeof CapabilityGuard>[0]["capability"];
  children: JSX.Element;
}) {
  return <CapabilityGuard capability={capability}>{children}</CapabilityGuard>;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route
              path="/login"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <LoginPage />
                </Suspense>
              }
            />
            <Route element={<AppLayout />}>
              <Route path="/" element={<GuardedRoute capability="dashboard:read"><Index /></GuardedRoute>} />
              <Route path="/reserve" element={<GuardedRoute capability="reserve:read"><ReservePage /></GuardedRoute>} />
              <Route path="/sku" element={<GuardedRoute capability="catalog:read"><SkuExplorerPage /></GuardedRoute>} />
              <Route path="/clients" element={<GuardedRoute capability="clients:read"><ClientsPage /></GuardedRoute>} />
              <Route path="/stock" element={<GuardedRoute capability="stock:read"><StockPage /></GuardedRoute>} />
              <Route path="/inbound" element={<GuardedRoute capability="inbound:read"><InboundPage /></GuardedRoute>} />
              <Route path="/uploads" element={<GuardedRoute capability="uploads:read"><UploadCenterPage /></GuardedRoute>} />
              <Route path="/mapping" element={<GuardedRoute capability="mapping:read"><MappingPage /></GuardedRoute>} />
              <Route path="/quality" element={<GuardedRoute capability="quality:read"><QualityPage /></GuardedRoute>} />
              <Route path="/ai" element={<GuardedRoute capability="assistant:query"><AiConsolePage /></GuardedRoute>} />
              <Route
                path="/admin"
                element={
                  <GuardedRoute capability="admin:read">
                    <AdminPage />
                  </GuardedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <GuardedRoute capability="settings:manage">
                    <SettingsPage />
                  </GuardedRoute>
                }
              />
            </Route>
            <Route path="/home" element={<Navigate to="/" replace />} />
            <Route
              path="*"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <NotFound />
                </Suspense>
              }
            />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;

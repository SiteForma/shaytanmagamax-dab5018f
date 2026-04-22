import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppShell } from "@/components/layout/AppShell";
import Index from "./pages/Index.tsx";
import NotFound from "./pages/NotFound.tsx";
import ReservePage from "@/features/reserve/ReservePage";
import SkuExplorerPage from "@/features/sku/SkuExplorerPage";
import ClientsPage from "@/features/clients/ClientsPage";
import StockPage from "@/features/stock/StockPage";
import InboundPage from "@/features/inbound/InboundPage";
import UploadCenterPage from "@/features/uploads/UploadCenterPage";
import MappingPage from "@/features/mapping/MappingPage";
import QualityPage from "@/features/quality/QualityPage";
import AiConsolePage from "@/features/assistant/AiConsolePage";
import SettingsPage from "@/features/settings/SettingsPage";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/reserve" element={<ReservePage />} />
            <Route path="/sku" element={<SkuExplorerPage />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/stock" element={<StockPage />} />
            <Route path="/inbound" element={<InboundPage />} />
            <Route path="/uploads" element={<UploadCenterPage />} />
            <Route path="/mapping" element={<MappingPage />} />
            <Route path="/quality" element={<QualityPage />} />
            <Route path="/ai" element={<AiConsolePage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthGuard } from "@/components/auth/AuthGuard";

const useCurrentUserQuery = vi.fn();
const useLogoutAction = vi.fn();
const getCurrentSession = vi.fn();
const isStrictAuthEnabled = vi.fn();

vi.mock("@/hooks/queries/use-auth", () => ({
  useCurrentUserQuery: () => useCurrentUserQuery(),
  useLogoutAction: () => useLogoutAction(),
}));

vi.mock("@/services/auth.service", () => ({
  getCurrentSession: () => getCurrentSession(),
}));

vi.mock("@/lib/auth/config", () => ({
  isStrictAuthEnabled: () => isStrictAuthEnabled(),
}));

function renderGuard(initialPath = "/stock") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[initialPath]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/login" element={<div>login-page</div>} />
          <Route
            path="*"
            element={
              <AuthGuard>
                <div>protected-app</div>
              </AuthGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AuthGuard", () => {
  beforeEach(() => {
    useCurrentUserQuery.mockReset();
    useLogoutAction.mockReset();
    getCurrentSession.mockReset();
    isStrictAuthEnabled.mockReset();
    useLogoutAction.mockReturnValue(vi.fn());
  });

  it("redirects to login when strict auth is enabled and session is missing", async () => {
    isStrictAuthEnabled.mockReturnValue(true);
    getCurrentSession.mockReturnValue(null);
    useCurrentUserQuery.mockReturnValue({ isLoading: false, error: null, data: null });

    render(renderGuard());

    expect(await screen.findByText("login-page")).toBeInTheDocument();
  });
});

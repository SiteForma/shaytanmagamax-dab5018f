import { fireEvent, screen } from "@testing-library/react";
import SettingsPage from "@/features/settings/SettingsPage";
import {
  SIDEBAR_MENU_LABELS_STORAGE_KEY,
  SIDEBAR_MENU_ORDER_STORAGE_KEY,
} from "@/lib/navigation-preferences";
import { renderWithProviders } from "@/test/render";

const useCurrentUserQuery = vi.fn();
const useLogoutAction = vi.fn();
const useUpdateCurrentUserProfileMutation = vi.fn();
const setTheme = vi.fn();

vi.mock("@/hooks/queries/use-auth", () => ({
  useCurrentUserQuery: () => useCurrentUserQuery(),
  useLogoutAction: () => useLogoutAction(),
  useUpdateCurrentUserProfileMutation: () => useUpdateCurrentUserProfileMutation(),
}));

vi.mock("@/lib/theme", () => ({
  useTheme: () => ({ theme: "dark", setTheme, toggle: vi.fn() }),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useCurrentUserQuery.mockReset();
    useLogoutAction.mockReset();
    useUpdateCurrentUserProfileMutation.mockReset();
    setTheme.mockReset();
    useCurrentUserQuery.mockReturnValue({ data: null });
    useLogoutAction.mockReturnValue(vi.fn());
    useUpdateCurrentUserProfileMutation.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
  });

  it("persists custom sidebar menu order from drag and drop", () => {
    renderWithProviders(<SettingsPage />, "/settings");

    const dragged = screen.getByLabelText("Перетащить пункт меню Центр загрузки");
    const target = screen.getByLabelText("Перетащить пункт меню ИИ-консоль");
    const dataTransfer = {
      effectAllowed: "",
      setData: vi.fn(),
      getData: vi.fn(() => "/uploads"),
    };

    fireEvent.dragStart(dragged, { dataTransfer });
    fireEvent.drop(target, { dataTransfer });

    const saved = JSON.parse(window.localStorage.getItem(SIDEBAR_MENU_ORDER_STORAGE_KEY) ?? "[]");
    expect(saved.indexOf("/uploads")).toBeLessThan(saved.indexOf("/ai"));
  });

  it("persists custom sidebar menu labels and can reset them", () => {
    renderWithProviders(<SettingsPage />, "/settings");

    fireEvent.change(screen.getByLabelText("Название пункта меню ИИ-консоль"), {
      target: { value: "Шайтан AI" },
    });

    expect(JSON.parse(window.localStorage.getItem(SIDEBAR_MENU_LABELS_STORAGE_KEY) ?? "{}")).toEqual({
      "/ai": "Шайтан AI",
    });

    fireEvent.click(screen.getByRole("button", { name: "Сбросить названия" }));
    expect(window.localStorage.getItem(SIDEBAR_MENU_LABELS_STORAGE_KEY)).toBeNull();
  });

  it("uses custom sidebar menu label as the current page title", () => {
    renderWithProviders(<SettingsPage />, "/settings");

    fireEvent.change(screen.getByLabelText("Название пункта меню Настройки"), {
      target: { value: "Параметры" },
    });

    expect(screen.getByRole("heading", { name: "Параметры", level: 1 })).toBeInTheDocument();
  });

  it("shows database-backed user profile controls instead of brand asset settings", () => {
    useCurrentUserQuery.mockReturnValue({
      data: {
        id: "user_1",
        email: "admin@magamax.local",
        fullName: "Сергей Селюк",
        firstName: "Сергей",
        lastName: "Селюк",
        roles: ["admin"],
        capabilities: [],
      },
    });

    renderWithProviders(<SettingsPage />, "/settings");

    expect(screen.queryByText("Брендовый ассет")).not.toBeInTheDocument();
    expect(screen.getByText("Пользователь")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Сергей")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Селюк")).toBeInTheDocument();
    expect(screen.getByDisplayValue("admin@magamax.local")).toBeInTheDocument();
    expect(screen.getByDisplayValue("admin")).toBeInTheDocument();
  });
});

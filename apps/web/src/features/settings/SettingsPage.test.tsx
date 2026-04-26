import { fireEvent, screen } from "@testing-library/react";
import SettingsPage from "@/features/settings/SettingsPage";
import {
  SIDEBAR_MENU_LABELS_STORAGE_KEY,
  SIDEBAR_MENU_ORDER_STORAGE_KEY,
} from "@/lib/navigation-preferences";
import { renderWithProviders } from "@/test/render";

const useCurrentUserQuery = vi.fn();
const useLogoutAction = vi.fn();
const setTheme = vi.fn();

vi.mock("@/hooks/queries/use-auth", () => ({
  useCurrentUserQuery: () => useCurrentUserQuery(),
  useLogoutAction: () => useLogoutAction(),
}));

vi.mock("@/lib/theme", () => ({
  useTheme: () => ({ theme: "dark", setTheme, toggle: vi.fn() }),
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useCurrentUserQuery.mockReset();
    useLogoutAction.mockReset();
    setTheme.mockReset();
    useCurrentUserQuery.mockReturnValue({ data: null });
    useLogoutAction.mockReturnValue(vi.fn());
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
});

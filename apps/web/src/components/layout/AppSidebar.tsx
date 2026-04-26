import { Link, useLocation } from "react-router-dom";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  Boxes,
  Building2,
  Calculator,
  LayoutDashboard,
  Settings,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Truck,
  Upload,
  Warehouse,
  Workflow,
} from "lucide-react";
import { MagamaxLogo } from "@/components/brand/MagamaxLogo";
import { useCurrentUserQuery } from "@/hooks/queries/use-auth";
import { hasCapability } from "@/lib/access";
import { NAV_SECTIONS, PRODUCT } from "@/lib/constants";
import {
  applyNavLabels,
  orderNavItems,
  useSidebarMenuLabels,
  useSidebarMenuOrder,
} from "@/lib/navigation-preferences";
import { cn } from "@/lib/utils";

const NAV_ICONS = {
  LayoutDashboard,
  Calculator,
  Boxes,
  Building2,
  Warehouse,
  Truck,
  Upload,
  Workflow,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Settings,
} as const;

export function AppSidebar() {
  const { pathname } = useLocation();
  const { state } = useSidebar();
  const { data: currentUser } = useCurrentUserQuery();
  const { order } = useSidebarMenuOrder();
  const { labels } = useSidebarMenuLabels();
  const collapsed = state === "collapsed";
  const navItems = applyNavLabels(
    orderNavItems(
      NAV_SECTIONS.filter((item) => !item.capability || hasCapability(currentUser, item.capability)),
      order,
    ),
    labels,
  );

  return (
    <Sidebar collapsible="icon" className="border-r border-line-subtle">
      <SidebarHeader
        className={cn(
          "border-b border-line-subtle py-3.5",
          collapsed ? "items-center px-0" : "px-3",
        )}
      >
        <MagamaxLogo showWordmark={!collapsed} className={cn(collapsed && "w-full justify-center")} />
      </SidebarHeader>

      <SidebarContent className={cn("py-3", collapsed ? "px-0" : "px-2")}>
        <SidebarGroup className={cn(collapsed && "items-center p-0")}>
          <SidebarGroupContent>
            <SidebarMenu className={cn(collapsed && "items-center gap-2")}>
              {navItems.map((item) => {
                const Icon = NAV_ICONS[item.icon];
                const active = item.path === "/" ? pathname === "/" : pathname.startsWith(item.path);
                return (
                  <SidebarMenuItem key={item.path} className={cn(collapsed && "flex justify-center")}>
                    <SidebarMenuButton asChild className={cn("h-9", collapsed && "mx-auto")} tooltip={collapsed ? item.label : undefined}>
                      <Link
                        to={item.path}
                        className={cn(
                          "group relative flex items-center gap-2.5 rounded-md px-2.5 text-[13px] font-medium",
                          collapsed && "justify-center gap-0 px-0",
                          active
                            ? "bg-surface-muted text-ink"
                            : "text-ink-secondary hover:bg-surface-muted/60 hover:text-ink",
                        )}
                      >
                        {active && !collapsed && (
                          <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-brand" />
                        )}
                        <Icon className={cn("h-4 w-4 shrink-0", active ? "text-brand" : "text-ink-muted")} />
                        <span className={cn("truncate", collapsed && "sr-only")}>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className={cn("border-t border-line-subtle", collapsed ? "items-center p-0 py-3" : "p-3")}>
        <div
          className={cn(
            "flex items-center gap-2 rounded-md bg-surface-muted/60",
            collapsed ? "h-8 w-8 justify-center px-0 py-0" : "justify-between px-2.5 py-2",
          )}
        >
          {!collapsed ? (
            <div className="flex flex-col leading-tight">
              <span className="text-[10px] uppercase tracking-[0.14em] text-ink-muted">{PRODUCT.org}</span>
              <span className="text-xs font-medium text-ink">{PRODUCT.name}</span>
            </div>
          ) : null}
          <span className="h-1.5 w-1.5 rounded-full bg-success shadow-[0_0_8px_hsl(var(--success))]" />
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}

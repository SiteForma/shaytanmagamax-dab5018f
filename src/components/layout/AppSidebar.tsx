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
} from "@/components/ui/sidebar";
import { MagamaxLogo } from "@/components/brand/MagamaxLogo";
import { NAV_SECTIONS, PRODUCT } from "@/lib/constants";
import * as Icons from "lucide-react";
import { cn } from "@/lib/utils";

export function AppSidebar() {
  const { pathname } = useLocation();

  return (
    <Sidebar collapsible="icon" className="border-r border-line-subtle">
      <SidebarHeader className="border-b border-line-subtle px-3 py-3.5">
        <MagamaxLogo />
      </SidebarHeader>

      <SidebarContent className="px-2 py-3">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_SECTIONS.map((item) => {
                const Icon = (Icons as any)[item.icon] as Icons.LucideIcon;
                const active = item.path === "/" ? pathname === "/" : pathname.startsWith(item.path);
                return (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton asChild className="h-9">
                      <Link
                        to={item.path}
                        className={cn(
                          "group relative flex items-center gap-2.5 rounded-md px-2.5 text-[13px] font-medium",
                          active
                            ? "bg-surface-muted text-ink"
                            : "text-ink-secondary hover:bg-surface-muted/60 hover:text-ink",
                        )}
                      >
                        {active && (
                          <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-brand" />
                        )}
                        <Icon className={cn("h-4 w-4 shrink-0", active ? "text-brand" : "text-ink-muted")} />
                        <span className="truncate">{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-line-subtle p-3">
        <div className="flex items-center justify-between gap-2 rounded-md bg-surface-muted/60 px-2.5 py-2">
          <div className="flex flex-col leading-tight">
            <span className="text-[10px] uppercase tracking-[0.14em] text-ink-muted">{PRODUCT.org}</span>
            <span className="text-xs font-medium text-ink">{PRODUCT.name}</span>
          </div>
          <span className="h-1.5 w-1.5 rounded-full bg-success shadow-[0_0_8px_hsl(var(--success))]" />
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}

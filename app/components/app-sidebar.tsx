import { NavLink, useLocation } from "react-router";
import { 
  Sidebar, 
  SidebarContent, 
  SidebarHeader, 
  SidebarFooter, 
  SidebarGroup, 
  SidebarGroupContent, 
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton
} from "~/components/ui/sidebar";
import { 
  Home, 
  StickyNote, 
  BarChart3, 
  Settings, 
  PenTool,
  User
} from "lucide-react";

export default function AppSidebar() {
  const location = useLocation();

  const navigationItems = [
    {
      title: "Home",
      url: "/",
      icon: Home,
    },
    {
      title: "Notes",
      url: "/notes",
      icon: StickyNote,
    },
    {
      title: "Analytics",
      url: "/analytics",
      icon: BarChart3,
    },
    {
      title: "Settings",
      url: "/settings",
      icon: Settings,
    }
  ];

  return (
    <Sidebar className="border-r border-zinc-200 dark:border-zinc-800">                
      <SidebarHeader className="flex flex-row items-center gap-3 px-6 py-4">
        <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-zinc-900 dark:bg-zinc-50 text-zinc-50 dark:text-zinc-950">
          <PenTool className="size-4" />
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="font-bold text-sm leading-none text-zinc-900 dark:text-zinc-50">Notes 2.0</span>
          <span className="text-[10px] text-zinc-400 font-medium">Workspace</span>
        </div>
      </SidebarHeader>

      <SidebarContent className="px-3">
        <SidebarGroup>
          <SidebarGroupLabel className="px-3 text-[10px] font-bold tracking-wider text-zinc-400 uppercase">
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent className="mt-2">
            <SidebarMenu className="gap-1">
              {navigationItems.map((item) => {
                const Icon = item.icon;
                const active = location.pathname === item.url;
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton 
                      render={<NavLink to={item.url} />} 
                      isActive={active}
                      className="rounded-xl transition-all duration-200"
                    >
                      <Icon className={`size-4 ${active ? 'text-zinc-900 dark:text-zinc-50' : 'text-zinc-500'}`} />
                      <span className={active ? 'font-semibold text-zinc-900 dark:text-zinc-50' : 'text-zinc-600 dark:text-zinc-300'}>
                        {item.title}
                      </span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-4 border-t border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center gap-3 px-2 py-1.5">
          <div className="flex aspect-square size-8 items-center justify-center rounded-full bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700">
            <User className="size-4 text-zinc-600 dark:text-zinc-400" />
          </div>
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className="font-semibold text-xs leading-none truncate text-zinc-900 dark:text-zinc-50">
              Timothy Shin
            </span>
            <span className="text-[10px] text-zinc-400 font-medium truncate capitalize">
              boss
            </span>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
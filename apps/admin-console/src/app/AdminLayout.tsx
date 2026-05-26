import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useLogout } from "@refinedev/core";
import {
  LayoutDashboard,
  FileText,
  GitBranch,
  Users,
  PhoneCall,
  Shield,
  CalendarClock,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
} from "lucide-react";

const navItems = [
  { to: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  {
    label: "Knowledge",
    icon: FileText,
    children: [
      { to: "/admin/knowledge/staging", label: "Staging" },
      { to: "/admin/knowledge/graph", label: "Graph" },
    ],
  },
  {
    label: "Campus",
    icon: CalendarClock,
    children: [
      { to: "/admin/campus/modules", label: "Operations" },
      { to: "/admin/campus/leaves", label: "Leaves" },
      { to: "/admin/campus/meals", label: "Meals" },
      { to: "/admin/campus/repairs", label: "Repairs" },
      { to: "/admin/campus/reports/daily", label: "Daily Report" },
    ],
  },
  { to: "/admin/crm/leads", label: "CRM Leads", icon: Users },
  { to: "/admin/sales/sessions", label: "Sales Sessions", icon: PhoneCall },
  { to: "/admin/audit", label: "Audit Log", icon: Shield },
];

export function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const { mutate: logout } = useLogout();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const sidebar = (
    <div
      className={`flex flex-col h-full bg-[#0a0a0a] border-r border-stone-800 transition-all duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      <div className="flex items-center justify-between h-14 px-4 border-b border-stone-800">
        {!collapsed && (
          <span className="text-amber-500 font-bold text-sm tracking-wide uppercase">
            Admin Console
          </span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex items-center justify-center w-6 h-6 rounded text-stone-500 hover:text-stone-200 hover:bg-stone-800"
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 space-y-1 px-2">
        {navItems.map((item) => {
          if ("children" in item && item.children) {
            return (
              <div key={item.label}>
                {!collapsed && (
                  <div className="sidebar-section-title">{item.label}</div>
                )}
                {item.children.map((child) => (
                  <NavLink
                    key={child.to}
                    to={child.to}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      `sidebar-link ${isActive ? "active" : ""} ${
                        collapsed ? "justify-center px-0" : ""
                      }`
                    }
                    title={collapsed ? child.label : undefined}
                  >
                    <item.icon size={18} />
                    {!collapsed && <span>{child.label}</span>}
                  </NavLink>
                ))}
              </div>
            );
          }
          return (
            <NavLink
              key={item.to}
              to={item.to!}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? "active" : ""} ${
                  collapsed ? "justify-center px-0" : ""
                }`
              }
              title={collapsed ? item.label : undefined}
            >
              <item.icon size={18} />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-stone-800 p-2">
        <button
          onClick={handleLogout}
          className={`sidebar-link w-full ${collapsed ? "justify-center px-0" : ""}`}
          title={collapsed ? "Logout" : undefined}
        >
          <LogOut size={18} />
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-[#0a0a0a] text-stone-200">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex shrink-0">{sidebar}</div>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full z-50">{sidebar}</div>
        </div>
      )}

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center justify-between h-12 px-4 border-b border-stone-800 bg-[#0a0a0a]">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1 text-stone-400 hover:text-stone-200"
          >
            <Menu size={20} />
          </button>
          <span className="text-amber-500 font-bold text-sm">Admin Console</span>
          <div className="w-6" />
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

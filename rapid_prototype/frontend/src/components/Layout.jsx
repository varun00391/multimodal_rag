import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BarChart3,
  Files,
  LogOut,
  MessageSquare,
  Plug,
  Settings,
} from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

const links = [
  { to: "/app/chat", label: "Ask", icon: MessageSquare },
  { to: "/app/library", label: "Library", icon: Files },
  { to: "/app/connectors", label: "Connectors", icon: Plug },
  { to: "/app/dashboard", label: "Usage", icon: BarChart3 },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-ink text-cream flex">
      <aside className="w-[232px] shrink-0 border-r border-line px-4 py-5 flex flex-col sticky top-0 h-screen overflow-y-auto">
        <div className="flex items-center gap-2.5 px-2 mb-8">
          <div className="h-8 w-8 rounded-lg bg-lime text-ink grid place-items-center font-serif text-xl">
            N
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">Nexus</div>
            <div className="text-[11px] text-mute">Knowledge OS</div>
          </div>
        </div>
        <nav className="space-y-1 flex-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm transition ${
                  isActive
                    ? "bg-white/10 text-cream"
                    : "text-mute hover:text-cream hover:bg-white/5"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="rounded-2xl border border-line p-3">
          <div className="text-sm font-medium truncate">{user?.name}</div>
          <div className="text-[11px] text-mute truncate mb-3">{user?.email}</div>
          <button
            onClick={() => {
              logout();
              navigate("/login");
            }}
            className="w-full flex items-center justify-center gap-2 text-xs rounded-lg border border-line py-2 hover:bg-white/5"
          >
            <LogOut size={13} /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0">
        <Outlet />
      </main>
    </div>
  );
}

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
  const initials = (user?.name || "N")
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="min-h-screen bg-ink text-cream p-3 flex gap-3">
      <aside className="w-[248px] shrink-0 rounded-shell bg-panel/80 backdrop-blur-xl border border-line shadow-lift px-4 py-5 flex flex-col sticky top-3 h-[calc(100vh-1.5rem)] overflow-y-auto">
        <div className="flex items-center gap-3 px-2 mb-8">
          <div className="h-9 w-9 rounded-xl bg-cream text-ink grid place-items-center font-serif text-lg italic">
            N
          </div>
          <div>
            <div className="text-[15px] font-medium tracking-tight">Nexus</div>
            <div className="text-[11px] text-mute">Knowledge OS</div>
          </div>
        </div>
        <nav className="space-y-1 flex-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2.5 rounded-full text-[13.5px] tracking-tight transition ${
                  isActive
                    ? "bg-cream text-ink shadow-lift"
                    : "text-mute hover:text-cream hover:bg-ink"
                }`
              }
            >
              <Icon size={16} strokeWidth={1.75} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="rounded-2xl bg-ink/80 border border-line p-3">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-9 w-9 rounded-full bg-mist/15 text-mist text-xs font-medium grid place-items-center">
              {initials}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">{user?.name}</div>
              <div className="text-[11px] text-mute truncate">{user?.email}</div>
            </div>
          </div>
          <button
            onClick={() => {
              logout();
              navigate("/login");
            }}
            className="btn-ghost w-full text-xs"
          >
            <LogOut size={13} /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 rounded-shell bg-panel/55 border border-line overflow-hidden min-h-[calc(100vh-1.5rem)]">
        <Outlet />
      </main>
    </div>
  );
}

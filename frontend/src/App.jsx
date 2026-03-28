import { Routes, Route, NavLink, useNavigate } from "react-router-dom";
import Browse from "./pages/Browse";
import Ingest from "./pages/Ingest";
import Search from "./pages/Search";
import Chat from "./pages/Chat";
import EntryDetail from "./pages/EntryDetail";
import EntityDetail from "./pages/EntityDetail";

const nav = [
  { to: "/", label: "Browse" },
  { to: "/ingest", label: "Add" },
  { to: "/search", label: "Search" },
  { to: "/chat", label: "Chat" },
];

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-neutral-800 px-6 py-4 flex items-center gap-8">
        <span className="text-lg font-semibold tracking-tight text-white">Big Brain</span>
        <nav className="flex gap-6">
          {nav.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `text-sm font-medium transition-colors ${
                  isActive ? "text-white" : "text-neutral-400 hover:text-neutral-200"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="flex-1 max-w-4xl w-full mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<Browse />} />
          <Route path="/ingest" element={<Ingest />} />
          <Route path="/search" element={<Search />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/entry/:id" element={<EntryDetail />} />
          <Route path="/entity/:id" element={<EntityDetail />} />
        </Routes>
      </main>
    </div>
  );
}

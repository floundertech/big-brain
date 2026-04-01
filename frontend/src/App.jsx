import { Routes, Route, NavLink, useNavigate } from "react-router-dom";
import Home from "./pages/Home";
import Browse from "./pages/Browse";
import Ingest from "./pages/Ingest";
import Search from "./pages/Search";
import Chat from "./pages/Chat";
import EntryDetail from "./pages/EntryDetail";
import EntityDetail from "./pages/EntityDetail";
import Entities from "./pages/Entities";
import Pipeline from "./pages/Pipeline";

const nav = [
  { to: "/", label: "Home" },
  { to: "/entries", label: "Browse" },
  { to: "/entities", label: "Entities" },
  { to: "/pipeline", label: "Pipeline" },
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
          <Route path="/" element={<Home />} />
          <Route path="/entries" element={<Browse />} />
          <Route path="/ingest" element={<Ingest />} />
          <Route path="/search" element={<Search />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/entry/:id" element={<EntryDetail />} />
          <Route path="/entities" element={<Entities />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/entity/:id" element={<EntityDetail />} />
        </Routes>
      </main>
    </div>
  );
}

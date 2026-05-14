import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Link, NavLink, useLocation } from "react-router-dom";
import "./index.css";
import SkillsPage from "./pages/SkillsPage";
import SkillDetailPage from "./pages/SkillDetailPage";
import MachinesPage from "./pages/MachinesPage";

function Header() {
  const loc = useLocation();
  const onSkill = loc.pathname.startsWith("/skills/");
  const linkCls = ({ isActive }: { isActive: boolean }) =>
    "px-3 py-1.5 rounded-md text-sm font-medium transition-colors " +
    (isActive
      ? "bg-[var(--surface-2)] text-[var(--text)]"
      : "text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface)]");
  return (
    <header className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--bg)]/85 backdrop-blur">
      <div className="max-w-6xl mx-auto px-5 h-14 flex items-center gap-5">
        <Link to="/" className="flex items-center gap-2 group">
          <span
            className="w-6 h-6 rounded-md grid place-items-center text-[10px] font-bold"
            style={{ background: "linear-gradient(135deg, #8b5cf6, #06b6d4)", color: "#0b0c10" }}
          >
            S
          </span>
          <span className="font-semibold tracking-tight">sync-skill</span>
        </Link>
        <nav className="flex items-center gap-1">
          <NavLink to="/" end className={linkCls}>Skills</NavLink>
          <NavLink to="/machines" className={linkCls}>Machines</NavLink>
        </nav>
        <div className="flex-1" />
        {!onSkill && (
          <a
            href="https://github.com/Restry/skills"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-[var(--muted)] hover:text-[var(--text)]"
          >
            github →
          </a>
        )}
      </div>
    </header>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Header />
      <main className="max-w-6xl mx-auto px-5 py-8">
        <Routes>
          <Route path="/" element={<SkillsPage />} />
          <Route path="/skills/:name" element={<SkillDetailPage />} />
          <Route path="/machines" element={<MachinesPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  </React.StrictMode>,
);

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Link, NavLink } from "react-router-dom";
import "./index.css";
import SkillsPage from "./pages/SkillsPage";
import SkillDetailPage from "./pages/SkillDetailPage";
import MachinesPage from "./pages/MachinesPage";

function Layout({ children }: { children: React.ReactNode }) {
  const linkCls = ({ isActive }: { isActive: boolean }) =>
    "px-3 py-2 rounded " +
    (isActive ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-200");
  return (
    <div className="min-h-screen">
      <header className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link to="/" className="font-semibold text-lg">sync-skill</Link>
          <nav className="flex gap-1">
            <NavLink to="/" end className={linkCls}>Skills</NavLink>
            <NavLink to="/machines" className={linkCls}>Machines</NavLink>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<SkillsPage />} />
          <Route path="/skills/:name" element={<SkillDetailPage />} />
          <Route path="/machines" element={<MachinesPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  </React.StrictMode>,
);

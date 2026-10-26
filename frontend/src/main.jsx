import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import "./index.css";
import Home from "./pages/Home";
import Items from "./pages/Items";
import Plan from "./pages/Plan";
import Delivery from "./pages/Delivery";

const LINKS = [
  ["/", "Home"],
  ["/items", "My Items"],
  ["/plan", "Order Plan"],
  ["/delivery", "Delivery & CO₂"],
];

function App() {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen">
      <header className="bg-brand-900 text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden><rect width="32" height="32" rx="7" fill="#059669" /><path d="M9 21c0-7 5-11 14-12-1 9-5 14-12 14" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" /></svg>
            <span className="font-semibold">Green Inventory Optimizer</span>
          </div>
          <button className="rounded p-2 sm:hidden" aria-label="Menu" aria-expanded={open} onClick={() => setOpen(!open)}>☰</button>
          <nav className={`${open ? "flex" : "hidden"} absolute left-0 right-0 top-14 z-[1000] flex-col bg-brand-900 px-4 pb-3 sm:static sm:flex sm:flex-row sm:gap-1 sm:p-0`}>
            {LINKS.map(([to, label]) => (
              <NavLink key={to} to={to} end onClick={() => setOpen(false)}
                className={({ isActive }) => `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-brand-700" : "text-brand-100 hover:bg-brand-800"}`}>
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/items" element={<Items />} />
          <Route path="/plan" element={<Plan />} />
          <Route path="/delivery" element={<Delivery />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-ink-500">
        Decision-support tool. Always check a plan before placing real orders. Maps © OpenStreetMap contributors.
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><App /></BrowserRouter>
  </React.StrictMode>
);

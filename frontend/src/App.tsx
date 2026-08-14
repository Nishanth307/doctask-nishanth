import { BrowserRouter, Navigate, Route, Routes, Link, Outlet } from "react-router-dom";
import RunsPage from "./pages/RunsPage";
import RunDetailsPage from "./pages/RunDetailsPage";
import "./App.css";

function Layout() {
  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">DocTask</div>
        <nav className="app-nav">
          <Link to="/runs">Runs</Link>
        </nav>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route 
            path="/runs" 
            element={<RunsPage />} 
          />
          <Route 
            path="/runs/:runId" 
            element={<RunDetailsPage />} 
          />
          <Route
            path="*"
            element={<Navigate to="/runs" replace />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
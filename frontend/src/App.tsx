import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import RunsPage from "./pages/RunsPage";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/runs" element={<RunsPage />} />

        <Route
          path="*"
          element={<Navigate to="/runs" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
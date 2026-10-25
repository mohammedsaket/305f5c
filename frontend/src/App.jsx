import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Shell, { MetaContext } from "./components/Shell";
import Accuracy from "./pages/Accuracy";
import Desk from "./pages/Desk";
import Method from "./pages/Method";

export default function App() {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/meta", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("The data service did not respond.");
        return response.json();
      })
      .then(setMeta)
      .catch((reason) => {
        if (reason.name !== "AbortError") setError(reason.message);
      });
    return () => controller.abort();
  }, []);

  if (error) {
    return (
      <p className="boot problem">
        {error} Start the API and reload this page.
      </p>
    );
  }
  if (!meta) return <p className="boot">Loading the January book.</p>;

  return (
    <MetaContext.Provider value={meta}>
      <BrowserRouter>
        <Shell>
          <Routes>
            <Route path="/" element={<Desk />} />
            <Route path="/accuracy" element={<Accuracy />} />
            <Route path="/method" element={<Method />} />
          </Routes>
        </Shell>
      </BrowserRouter>
    </MetaContext.Provider>
  );
}

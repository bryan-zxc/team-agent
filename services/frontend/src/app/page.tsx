"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [health, setHealth] = useState<string>("checking...");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetch(`${apiUrl}/health`)
      .then((res) => res.json())
      .then((data) => setHealth(JSON.stringify(data, null, 2)))
      .catch((err) => setHealth(`error: ${err.message}`));
  }, [apiUrl]);

  return (
    <main style={{ padding: "2rem", fontFamily: "monospace" }}>
      <h1>Team Agent</h1>
      <h2>API Health</h2>
      <pre>{health}</pre>
    </main>
  );
}

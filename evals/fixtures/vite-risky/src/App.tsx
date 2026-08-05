import { useState } from "react";

export function App() {
  const [html] = useState("<strong>hello</strong>");
  return (
    <main>
      <h1>Fixture</h1>
      <input placeholder="Search" />
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </main>
  );
}

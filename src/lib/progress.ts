import { useEffect, useState } from "react";

export function useDone() {
  const [done, setDone] = useState<string[]>([]);
  useEffect(() => { try { setDone(JSON.parse(localStorage.getItem("learn-done") ?? "[]")); } catch { /* ignore */ } }, []);
  const mark = (id: string) => setDone((d) => { const n = d.includes(id) ? d : [...d, id]; localStorage.setItem("learn-done", JSON.stringify(n)); return n; });
  return { done, mark };
}


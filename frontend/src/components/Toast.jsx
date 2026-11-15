import { createContext, useCallback, useContext, useState } from "react";
import Icon from "./Icon.jsx";

const ToastContext = createContext({ toast: () => {} });
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const toast = useCallback((text, kind = "ok") => {
    const id = Math.random().toString(36).slice(2);
    setItems((list) => [...list, { id, text, kind }]);
    setTimeout(() => setItems((list) => list.filter((i) => i.id !== id)), 3800);
  }, []);
  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className={`toast ${i.kind}`}>
            <Icon name={i.kind === "err" ? "close" : "check"} size={18} />
            <span>{i.text}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

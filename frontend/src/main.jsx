import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./lib/auth";
import "./styles.css";

// On a computer the app is shown as a 390 x 844 phone, scaled down to fit the window (see .app in styles.css).
function fitPhone() {
  const scale = Math.min(1, (window.innerHeight - 48) / 844, (window.innerWidth - 48) / 390);
  document.documentElement.style.setProperty("--phone-scale", String(Math.max(scale, 0.3)));
}
fitPhone();
window.addEventListener("resize", fitPhone);

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);

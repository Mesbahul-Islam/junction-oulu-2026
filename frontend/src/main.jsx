import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { Providers } from "@/app/providers";
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
      <Providers>
        <App />
      </Providers>
    </BrowserRouter>
  </StrictMode>,
);

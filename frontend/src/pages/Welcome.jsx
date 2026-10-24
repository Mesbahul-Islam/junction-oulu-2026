import { ArrowRight, Newspaper } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth";

// Local demo accounts created by `manage.py bootstrap` (see docs/GUIDE.md).
const DEMO = [
  { email: "newcomer@example.com", password: "demo-reader", label: "Demo: newcomer (reads Ukrainian)" },
  { email: "fan@example.com", password: "demo-reader", label: "Demo: local sports fan (reads Finnish)" },
];

export default function Welcome() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const go = (user) => navigate(user?.onboarded ? location.state?.from || "/" : `/onboarding${location.search}`, { replace: true });

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      go(mode === "signup" ? await register(email, password) : await login(email, password));
    } catch (err) {
      const data = err.data || {};
      setError(data.email?.[0] || data.password?.[0] || data.non_field_errors?.[0] || err.message);
    } finally {
      setBusy(false);
    }
  };

  const demo = async (d) => {
    setBusy(true);
    try {
      go(await login(d.email, d.password));
    } catch (err) {
      setError(`${err.message}. Is the backend running with demo data?`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="screen">
      <div className="back-row">
        <div className="avatar"><Newspaper size={22} /></div>
        <h1>Oulu News</h1>
      </div>
      <h2 className="title-serif">Local news, in your language</h2>
      <p className="lead">Reviewed by editors, explained for your situation, ranked for you.</p>

      <form className="panel" onSubmit={submit}>
        {error && <div className="error">{error}</div>}
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete={mode === "signup" ? "new-password" : "current-password"}
            required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <button className="btn-primary" disabled={busy}>
          {mode === "signup" ? "Create account" : "Log in"} <ArrowRight size={18} />
        </button>
        <p style={{ textAlign: "center", margin: "14px 0 0", fontSize: 14 }}>
          {mode === "signup" ? "Already have an account? " : "New here? "}
          <button type="button" className="btn-link" onClick={() => setMode(mode === "signup" ? "login" : "signup")}>
            {mode === "signup" ? "Log in" : "Create one"}
          </button>
        </p>
      </form>

      <div className="demo-buttons">
        {DEMO.map((d) => (
          <button key={d.email} className="btn-ghost" disabled={busy} onClick={() => demo(d)}>{d.label}</button>
        ))}
      </div>
    </main>
  );
}

import { ArrowRight, Newspaper } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { API_URL, token } from "../lib/api";
import { useAuth } from "../lib/auth";

// Local demo accounts created by `manage.py bootstrap` (see docs/GUIDE.md).
const DEMO = [
  { email: "newcomer@example.com", password: "demo-reader", label: "Demo: newcomer (reads Ukrainian)" },
  { email: "fan@example.com", password: "demo-reader", label: "Demo: local sports fan (reads Finnish)" },
];

export default function Welcome() {
  const { login, register, refresh } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const go = (user) => navigate(user?.onboarded ? location.state?.from || "/" : `/onboarding${location.search}`, { replace: true });

  // Handle OAuth callback token in URL hash (#token=...)
  useEffect(() => {
    const hash = window.location.hash;
    if (hash.includes("token=")) {
      const params = new URLSearchParams(hash.replace(/^#/, ""));
      const t = params.get("token");
      if (t) {
        token.set(t);
        window.history.replaceState(null, "", window.location.pathname + window.location.search);
        refresh().then((user) => {
          if (user) go(user);
        });
      }
    }
  }, [refresh]);

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

        <div className="auth-divider"><span>or</span></div>

        <a href={`${API_URL}/accounts/google/login/?next=/accounts/oauth/callback/?next=frontend`} className="btn-google">
          <svg width="18" height="18" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
          </svg>
          Continue with Google
        </a>

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

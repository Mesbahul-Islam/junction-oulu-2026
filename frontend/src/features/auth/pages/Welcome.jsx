import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { Wordmark } from "@/components/patterns";
import { Button, Field, Input } from "@/components/ui";
import { API_URL, token } from "@/lib/api";

import { useAuth } from "../AuthProvider";

// Local demo accounts created by `manage.py bootstrap` (see docs/GUIDE.md).
const DEMO = {
  newcomer: { email: "newcomer@example.com", password: "demo-reader" },
  fan: { email: "fan@example.com", password: "demo-reader" },
};

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
    </svg>
  );
}

/** Log in / sign up, Notion-login style: quiet top bar, one centred column with lots of air,
 *  Google first, email second, demo accounts as quiet links. Phones get the same order, roomier controls. */
export default function Welcome() {
  const { login, register, refresh } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const go = (user) =>
    navigate(user?.onboarded ? location.state?.from || "/" : `/onboarding${location.search}`, { replace: true });

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

  const run = async (work, hint = "") => {
    setBusy(true);
    setError("");
    try {
      go(await work());
    } catch (err) {
      const data = err.data || {};
      setError((data.username?.[0] || data.email?.[0] || data.password?.[0] || data.non_field_errors?.[0] || err.message) + hint);
    } finally {
      setBusy(false);
    }
  };

  const isSignup = mode === "signup";
  const submit = (event) => {
    event.preventDefault();
    run(() => (isSignup ? register(email, username.trim(), password) : login(email, password)));
  };
  const demo = (d) => run(() => login(d.email, d.password), ". Is the backend running with demo data?");
  const switchMode = () => { setMode(isSignup ? "login" : "signup"); setError(""); };

  return (
    <div className="flex min-h-dvh flex-col bg-paper font-sans text-ink">
      <header className="flex h-14 items-center px-5 pt-[env(safe-area-inset-top)] md:px-6">
        <Wordmark />
      </header>

      <main className="flex flex-1 flex-col items-center px-5 pb-12 pt-10 md:pt-[12vh]">
        <div className="flex max-w-xl flex-col items-center gap-2 text-center">
          <h1 className="text-display text-balance md:text-hero">Local news, in your language.</h1>
          <p className="text-ui text-muted">
            {isSignup ? "Create an account to get Oulu's news explained for you." : "Log in to read today's stories."}
          </p>
        </div>

        <div className="mt-10 flex w-full max-w-[340px] flex-col gap-4">
          <Button asChild variant="secondary" size="lg" block>
            <a href={`${API_URL}/accounts/google/login/?next=/accounts/oauth/callback/?next=frontend`}>
              <GoogleIcon />Continue with Google
            </a>
          </Button>

          <div className="flex items-center gap-3 text-caption text-muted" aria-hidden="true">
            <span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" />
          </div>

          <form className="flex flex-col gap-3.5" onSubmit={submit}>
            {error && <p role="alert" className="rounded-control bg-danger-weak px-3 py-2 text-meta text-danger">{error}</p>}
            <Field label="Email" htmlFor="email">
              <Input id="email" type="email" autoComplete="email" required placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            {isSignup && (
              <Field label="Username" htmlFor="username" hint="Shown on your posts and comments.">
                <Input
                  id="username"
                  autoComplete="username"
                  required
                  minLength={3}
                  maxLength={30}
                  pattern="[A-Za-z0-9_.]{3,30}"
                  title="3–30 letters, digits, _ or ."
                  value={username}
                  onChange={(e) => setUsername(e.target.value.replace(/\s/g, ""))}
                />
              </Field>
            )}
            <Field label="Password" htmlFor="password" hint={isSignup ? "At least 8 characters." : undefined}>
              <Input
                id="password"
                type="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <Button type="submit" size="lg" block disabled={busy} className="mt-1">
              {isSignup ? "Create account" : "Log in"}
            </Button>
          </form>

          <p className="text-center text-meta text-muted">
            {isSignup ? "Already have an account? " : "New here? "}
            <Button variant="link" className="text-meta" onClick={switchMode}>{isSignup ? "Log in" : "Create an account"}</Button>
          </p>

          <p className="mt-6 border-t border-line pt-6 text-center text-meta text-muted">
            Just looking? Try it as a{" "}
            <Button variant="link" className="text-meta" disabled={busy} onClick={() => demo(DEMO.newcomer)}>newcomer reading Ukrainian</Button>
            {" "}or a{" "}
            <Button variant="link" className="text-meta" disabled={busy} onClick={() => demo(DEMO.fan)}>sports fan reading Finnish</Button>.
          </p>
        </div>
      </main>

      <footer className="px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] text-center text-caption text-muted">
        Every story is checked by an editor before it's published.
      </footer>
    </div>
  );
}

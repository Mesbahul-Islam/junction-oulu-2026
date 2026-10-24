import { ArrowRight, Newspaper, ShieldCheck, Sparkles, Languages as LanguagesIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { Button, Card, Field, Input } from "@/components/ui";
import { API_URL, token } from "@/lib/api";
import { LANGUAGES } from "@/lib/i18n";

import { useAuth } from "../AuthProvider";

// Local demo accounts created by `manage.py bootstrap` (see docs/GUIDE.md).
const DEMO = [
  { email: "newcomer@example.com", password: "demo-reader", label: "Newcomer · reads Ukrainian" },
  { email: "fan@example.com", password: "demo-reader", label: "Local sports fan · reads Finnish" },
];

const PROMISES = [
  { icon: ShieldCheck, text: "Reviewed by editors — never auto-published." },
  { icon: Sparkles, text: "Explained for your situation, not just translated." },
  { icon: LanguagesIcon, text: "In the language you read best." },
];

function Promises() {
  return (
    <ul className="flex flex-col gap-2.5">
      {PROMISES.map(({ icon: Icon, text }) => (
        <li key={text} className="flex items-center gap-3 text-[15px]">
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent-weak text-accent">
            <Icon size={15} />
          </span>
          {text}
        </li>
      ))}
    </ul>
  );
}

function LanguageChips() {
  return (
    <div className="flex flex-wrap gap-1.5" aria-label="Available languages">
      {LANGUAGES.map((l) => (
        <span key={l.code} dir="auto" className="rounded-pill border border-line bg-surface px-2.5 py-1 text-xs font-medium text-muted">
          {l.name}
        </span>
      ))}
    </div>
  );
}

export default function Welcome() {
  const { login, register, refresh } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState("signup");
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

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      go(mode === "signup" ? await register(email, username.trim(), password) : await login(email, password));
    } catch (err) {
      const data = err.data || {};
      setError(data.username?.[0] || data.email?.[0] || data.password?.[0] || data.non_field_errors?.[0] || err.message);
    } finally {
      setBusy(false);
    }
  };

  const demo = async (d) => {
    setBusy(true);
    setError("");
    try {
      go(await login(d.email, d.password));
    } catch (err) {
      setError(`${err.message}. Is the backend running with demo data?`);
    } finally {
      setBusy(false);
    }
  };

  const isSignup = mode === "signup";

  return (
    <main className="grid min-h-dvh grid-cols-1 bg-paper text-ink lg:grid-cols-2">
      {/* Brand — compact on mobile, full value panel on desktop */}
      <section className="flex flex-col justify-center gap-6 px-6 pb-2 pt-[max(2rem,env(safe-area-inset-top))] lg:min-h-dvh lg:gap-9 lg:px-14 lg:py-16">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-md bg-ink text-paper">
            <Newspaper size={18} />
          </span>
          <span className="text-lg font-bold tracking-tight">Oulu News</span>
        </div>

        <div className="flex flex-col gap-3">
          <h1 className="text-balance text-[2rem] font-bold leading-[1.05] tracking-tight sm:text-4xl lg:text-5xl">
            Local news, in your language.
          </h1>
          <p className="max-w-md text-[15px] text-muted lg:text-lg">
            Reviewed by Oulu editors, explained for where you are in life, and ranked for what actually affects you.
          </p>
        </div>

        {/* Value bits live in the panel on desktop only; on mobile they sit below the form */}
        <div className="hidden lg:flex lg:flex-col lg:gap-9">
          <Promises />
          <LanguageChips />
        </div>
      </section>

      {/* Auth form */}
      <section className="flex items-start justify-center px-6 py-6 lg:min-h-dvh lg:items-center lg:px-14 lg:py-16">
        <Card variant="float" className="w-full max-w-md p-6 sm:p-7">
          <h2 className="text-xl font-semibold">{isSignup ? "Create your account" : "Welcome back"}</h2>
          <p className="mt-1 text-sm text-muted">
            {isSignup ? "A minute to set up — then the news comes to you." : "Pick up where you left off."}
          </p>

          <form className="mt-6 flex flex-col gap-4" onSubmit={submit}>
            {error && (
              <div role="alert" className="rounded-md bg-danger/10 px-3 py-2.5 text-sm font-medium text-danger">
                {error}
              </div>
            )}

            <Field label="Email" htmlFor="email">
              <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            </Field>

            {isSignup && (
              <Field label="Username" htmlFor="username" hint={`Shown as @${username || "username"} on your posts and comments.`}>
                <Input
                  id="username"
                  autoComplete="username"
                  required
                  minLength={3}
                  maxLength={30}
                  pattern="[A-Za-z0-9_.]{3,30}"
                  title="3–30 letters, digits, _ or ."
                  placeholder="e.g. aino_oulu"
                  value={username}
                  onChange={(e) => setUsername(e.target.value.replace(/\s/g, ""))}
                />
              </Field>
            )}

            <Field label="Password" htmlFor="password">
              <Input
                id="password"
                type="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
              />
            </Field>

            <Button type="submit" size="lg" block disabled={busy}>
              {isSignup ? "Create account" : "Log in"} <ArrowRight size={18} />
            </Button>
          </form>

          <div className="my-5 flex items-center gap-3 text-xs text-muted">
            <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
          </div>

          <a
            href={`${API_URL}/accounts/google/login/?next=/accounts/oauth/callback/?next=frontend`}
            className="flex h-12 w-full items-center justify-center gap-2.5 rounded-pill border border-line bg-surface text-[15px] font-semibold text-ink transition-colors hover:bg-ink/[0.03]"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
            </svg>
            Continue with Google
          </a>

          <p className="mt-5 text-center text-sm text-muted">
            {isSignup ? "Already have an account? " : "New here? "}
            <button type="button" className="font-semibold text-accent hover:underline" onClick={() => { setMode(isSignup ? "login" : "signup"); setError(""); }}>
              {isSignup ? "Log in" : "Create one"}
            </button>
          </p>

          <div className="mt-6 border-t border-line pt-5">
            <p className="mb-2.5 text-center text-xs font-medium uppercase tracking-wide text-muted">Try a demo account</p>
            <div className="flex flex-col gap-2">
              {DEMO.map((d) => (
                <Button key={d.email} variant="ghost" size="sm" block disabled={busy} onClick={() => demo(d)}>
                  {d.label}
                </Button>
              ))}
            </div>
          </div>
        </Card>
      </section>

      {/* Value bits — mobile only (desktop shows them in the brand panel) */}
      <section className="flex flex-col gap-6 px-6 pb-[max(2.5rem,env(safe-area-inset-bottom))] pt-1 lg:hidden">
        <Promises />
        <LanguageChips />
      </section>
    </main>
  );
}

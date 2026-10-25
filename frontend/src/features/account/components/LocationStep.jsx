import { Check, LocateFixed, MapPin, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, Input, Spinner } from "@/components/ui";
import { getMunicipalities, getMunicipality, locate } from "@/features/account/api";
import { cn } from "@/lib/utils";

const GEO_OPTIONS = { enableHighAccuracy: false, timeout: 15000, maximumAge: 10 * 60 * 1000 };

function geoError(err) {
  if (!err) return "Your browser can't share a location here. Choose your town instead.";
  if (err.code === 1) return "Location is turned off for this site. You can choose your town instead.";
  if (err.code === 3) return "Finding your location took too long. Try again, or choose your town.";
  return "We couldn't find your location. Choose your town instead.";
}

/** Onboarding: find the reader's municipality from the browser's location (asked only when they
 *  tap the button), or let them pick it. `town` is what /accounts/locate/ returns. */
export function LocationStep({ town, onTown }) {
  const [status, setStatus] = useState(town ? "found" : "idle"); // idle | asking | found | error
  const [message, setMessage] = useState("");
  const [picking, setPicking] = useState(false);

  const useMyLocation = () => {
    if (!("geolocation" in navigator) || !window.isSecureContext) {
      setStatus("error");
      setMessage(geoError(null));
      setPicking(true);
      return;
    }
    setStatus("asking");
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          onTown(await locate(coords.latitude, coords.longitude));
          setStatus("found");
          setPicking(false);
        } catch (err) {
          setStatus("error");
          setMessage(err.status === 404 ? "You seem to be outside Finland. Choose the town you live in." : geoError({}));
          setPicking(true);
        }
      },
      (err) => {
        setStatus("error");
        setMessage(geoError(err));
        setPicking(true);
      },
      GEO_OPTIONS,
    );
  };

  const choose = async (code) => {
    onTown(await getMunicipality(code));
    setStatus("found");
    setPicking(false);
  };

  return (
    <div className="flex flex-col gap-4">
      {status === "found" && town ? (
        <TownResult town={town} onChange={() => setPicking(true)} />
      ) : (
        <div className="flex flex-col gap-4 rounded-card border border-line bg-surface p-5 sm:p-6">
          <div className="flex gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-sunk">
              <MapPin size={20} />
            </span>
            <div className="flex flex-col gap-1">
              <p className="text-title">Local news needs your location</p>
              <p className="text-ui text-muted">
                Your browser will ask for permission. We use your location once to find your municipality, and keep only the town name, never where you are.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="lg" onClick={useMyLocation} disabled={status === "asking"}>
              {status === "asking" ? <Spinner className="h-4 w-4" /> : <LocateFixed size={16} />}
              {status === "asking" ? "Finding your municipality…" : "Use my location"}
            </Button>
            {!picking && (
              <Button variant="link" onClick={() => setPicking(true)}>Choose my town instead</Button>
            )}
          </div>
          {status === "error" && (
            <p role="alert" className="text-meta text-muted">{message}</p>
          )}
        </div>
      )}
      {picking && <TownPicker onPick={choose} />}
    </div>
  );
}

function TownResult({ town, onChange }) {
  return (
    <div className="flex flex-col gap-4 rounded-card border border-newsroom/40 bg-newsroom-weak/50 p-5 sm:p-6" aria-live="polite">
      <div className="flex gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-newsroom text-on-ink">
          <Check size={20} />
        </span>
        <div className="flex flex-col gap-1">
          <p className="text-meta text-muted">Your municipality</p>
          <p className="text-headline">{town.name}</p>
        </div>
      </div>
      {town.covered ? (
        <p className="text-ui">We'll show you local news from {town.name}, in your language.</p>
      ) : (
        <p className="text-ui">
          We don't have a newsroom for {town.name} yet. Until we do, you'll see news from{" "}
          <span className="font-semibold">{town.nearest?.name}</span>, the nearest town we cover
          {town.nearest?.km ? ` (${town.nearest.km} km away)` : ""}.
        </p>
      )}
      <div>
        <Button variant="link" onClick={onChange}>Not right? Choose your town</Button>
      </div>
    </div>
  );
}

function TownPicker({ onPick }) {
  const [all, setAll] = useState(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    getMunicipalities().then(setAll).catch(() => setAll([]));
  }, []);

  const matches = useMemo(() => {
    if (!all) return [];
    const q = query.trim().toLowerCase();
    const list = q ? all.filter((m) => m.name.toLowerCase().includes(q)) : all.filter((m) => m.covered);
    return [...list].sort((a, b) => Number(b.name.toLowerCase().startsWith(q)) - Number(a.name.toLowerCase().startsWith(q))).slice(0, 8);
  }, [all, query]);

  const pick = async (code) => {
    setBusy(code);
    try {
      await onPick(code);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <label htmlFor="town-search" className="text-meta font-medium">Your municipality</label>
      <div className="relative">
        <Search size={16} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted" />
        <Input
          id="town-search"
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search, e.g. Kemi"
          className="ps-9"
          autoComplete="address-level2"
        />
      </div>
      {all === null ? (
        <Spinner />
      ) : (
        <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
          {matches.length === 0 && <li className="px-4 py-3 text-ui text-muted">No municipality matches "{query}".</li>}
          {matches.map((m) => (
            <li key={m.code}>
              <button
                type="button"
                onClick={() => pick(m.code)}
                disabled={!!busy}
                className={cn("focus-ring flex w-full items-center justify-between gap-3 px-4 py-3 text-start text-ui hover:bg-ink/[0.03]",
                  "[@media(pointer:coarse)]:min-h-11")}
              >
                <span>{m.name}</span>
                {busy === m.code ? <Spinner className="h-4 w-4" /> : m.covered && <Badge tone="newsroom">Local newsroom</Badge>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

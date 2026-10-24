import { Bookmark, Compass, House, Plus, User } from "lucide-react";
import { NavLink } from "react-router-dom";

const ITEMS = [
  { to: "/", label: "Home", icon: House },
  { to: "/explore", label: "Discover", icon: Compass },
  { to: "/create", label: "Create", icon: Plus, create: true },
  { to: "/saved", label: "Saved", icon: Bookmark },
  { to: "/profile", label: "Profile", icon: User },
];

/** TikTok-style bottom bar with a centre "+" (post, or send a tip to the newsroom). */
export default function BottomNav() {
  return (
    <nav className="tt-nav" aria-label="Main">
      {ITEMS.map(({ to, label, icon: Icon, create }) => (
        <NavLink key={to} to={to} end aria-label={label} className={({ isActive }) => `tt-nav-item${isActive ? " active" : ""}${create ? " create" : ""}`}>
          {create ? <span className="tt-plus"><Icon size={22} strokeWidth={2.4} /></span> : <Icon size={23} strokeWidth={1.8} />}
          {!create && <span>{label}</span>}
        </NavLink>
      ))}
    </nav>
  );
}

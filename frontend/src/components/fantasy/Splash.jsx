import { useT } from "../../lib/lamariText";
import { LAMARI_POSTER } from "./util";

/** Lämäri load screen, shown while sports data arrives (at least a few seconds, once per visit). */
export default function Splash({ leaving }) {
  const t = useT();
  return (
    <div className={`fx-splash${leaving ? " out" : ""}`} role="status" aria-label={t("loading")}>
      <img src={LAMARI_POSTER} alt="Lämäri. Pelaa. Voita. Jääkiekkoa." />
      <div className="fx-splash-bar"><span /></div>
    </div>
  );
}

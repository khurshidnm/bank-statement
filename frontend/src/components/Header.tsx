import { Sparkles } from "lucide-react";

export default function Header() {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/15 text-accent">
          <Sparkles size={18} />
        </div>
        <div>
          <h1 className="text-base font-semibold text-white">
            Universal Data Normalizer
          </h1>
          <p className="text-xs text-muted">
            Excel &middot; CSV &middot; JSON &rarr; Standardized Target JSON
          </p>
        </div>
      </div>
    </header>
  );
}

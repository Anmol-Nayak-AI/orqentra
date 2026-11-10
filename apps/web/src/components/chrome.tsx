import { Link } from "react-router-dom";
import { Sun, Moon } from "lucide-react";
import { Button } from "./ui/button";
export function Brand() {
  return (
    <Link to="/" aria-label="Orqentra home" className="flex items-center gap-3">
      <span className="grid size-9 place-items-center rounded-xl bg-[var(--accent)] font-bold text-[#09251c]">
        O
      </span>
      <span className="text-xl font-semibold tracking-tight">
        orqentra<span className="text-[var(--accent)]">.</span>
      </span>
    </Link>
  );
}

export function ThemeToggle({ dark, toggle }: { dark: boolean; toggle: () => void }) {
  return (
    <Button
      variant="outline"
      size="icon"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={toggle}
    >
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  );
}

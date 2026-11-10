import { createContext } from "react";
import { Link, Outlet } from "react-router-dom";
import { ArrowLeft, Building2, Layers3, ShieldCheck } from "lucide-react";
import { Brand, ThemeToggle } from "../components/chrome";

export const AuthenticationTheme = createContext(true);

export function AuthenticationLayout({ dark, toggle }: { dark: boolean; toggle: () => void }) {
  return (
    <AuthenticationTheme.Provider value={dark}>
      <div className="auth-layout">
        <aside className="auth-story" aria-label="About Orqentra">
          <Brand />
          <div className="auth-story-content">
            <p className="auth-eyebrow">
              <span /> THE ENTERPRISE AI WORKFORCE
            </p>
            <h1>
              Your workforce,
              <br />
              <span className="auth-headline-accent">
                intelligently
                <br />
                orchestrated.
              </span>
            </h1>
            <p className="auth-story-description">
              A shared home for your people, workspaces, and the AI teammates you’re building.
            </p>
            <div className="auth-architecture" aria-hidden="true">
              <div className="auth-architecture-heading">
                <span className="auth-line" /> CONNECTED BY DESIGN
              </div>
              <div className="auth-organization-node">
                <Building2 size={18} />
                <span>Your organization</span>
                <span className="auth-node-mark">O</span>
              </div>
              <div className="auth-connectors">
                <span />
                <span />
              </div>
              <div className="auth-architecture-branches">
                <div>
                  <Layers3 size={17} />
                  <span>Shared workspaces</span>
                </div>
                <div>
                  <ShieldCheck size={17} />
                  <span>Controlled access</span>
                </div>
              </div>
            </div>
          </div>
          <div className="auth-story-footer">
            <span>Orqentra</span>
            <span>Clarity. Coordination. Control.</span>
          </div>
        </aside>
        <main id="main" tabIndex={-1} className="auth-panel">
          <nav className="auth-toolbar" aria-label="Authentication navigation">
            <Link to="/">
              <ArrowLeft size={15} /> Back to home
            </Link>
            <ThemeToggle dark={dark} toggle={toggle} />
          </nav>
          <div className="auth-panel-content">
            <p className="auth-access-label">
              <ShieldCheck size={14} /> YOUR ORGANIZATION STARTS HERE
            </p>
            <Outlet />
          </div>
          <p className="auth-panel-footer">Your workspace. Your team. One place.</p>
        </main>
      </div>
    </AuthenticationTheme.Provider>
  );
}

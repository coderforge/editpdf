import { useEffect } from "react";
import { LANGUAGES, format, useI18n, type Language } from "./i18n";
import { LogoMark, MergeIcon, RotateIcon, SplitIcon } from "./components/icons";
import { NotFoundPage, TermsPage } from "./pages/TermsPage";
import { Link, useRoute, type Route } from "./router";
import { MergeTool } from "./tools/MergeTool";
import { RotateTool } from "./tools/RotateTool";
import { SplitTool } from "./tools/SplitTool";

const REPOSITORY = "https://github.com/coderforge/editpdf";

const TOOLS = [
  { route: "merge", Icon: MergeIcon },
  { route: "split", Icon: SplitIcon },
  { route: "rotate", Icon: RotateIcon },
] as const;

function Header({ route }: { readonly route: Route }) {
  const { t, language, setLanguage } = useI18n();
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link to="merge" className="brand" aria-label="editpdf">
          <LogoMark />
          <span className="brand__name">editpdf</span>
        </Link>
        <span className="brand__tagline">{t.tagline}</span>
        <nav className="tabs" aria-label={t.nav.tools}>
          {TOOLS.map(({ route: target, Icon }) => (
            <Link key={target} to={target} className={`tab${route === target ? " tab--active" : ""}`} aria-current={route === target ? "page" : undefined}>
              <Icon width={18} height={18} />
              <span>{t.nav[target]}</span>
            </Link>
          ))}
        </nav>
        <label className="language">
          <span className="visually-hidden">{t.nav.language}</span>
          <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
            {(Object.keys(LANGUAGES) as Language[]).map((code) => (
              <option key={code} value={code}>
                {LANGUAGES[code].languageName}
              </option>
            ))}
          </select>
        </label>
      </div>
    </header>
  );
}

function Footer() {
  const { t } = useI18n();
  return (
    <footer className="site-footer">
      <p className="site-footer__privacy">{t.privacy}</p>
      <p className="site-footer__disclaimer">{t.footer.disclaimer}</p>
      <p className="site-footer__links">
        <span>{format(t.footer.copyright, { year: new Date().getFullYear() })}</span>
        <a href={`${REPOSITORY}/blob/main/LICENSE`} target="_blank" rel="noopener noreferrer">
          {t.footer.license}
        </a>
        <Link to="terms">{t.footer.terms}</Link>
        <a href="/api/v1/openapi.yaml">{t.footer.api}</a>
        <a href={REPOSITORY} target="_blank" rel="noopener noreferrer">
          {t.footer.source}
        </a>
      </p>
    </footer>
  );
}

export function App() {
  const route = useRoute();
  const { t, language } = useI18n();

  useEffect(() => {
    document.documentElement.lang = language;
    if (route !== "terms") {
      document.title = route === "not-found" ? "editpdf" : `${t[route].title} - editpdf`;
    }
  }, [route, language, t]);

  return (
    <div className="app">
      <Header route={route} />
      <main className="main">
        {route === "merge" ? <MergeTool /> : null}
        {route === "split" ? <SplitTool /> : null}
        {route === "rotate" ? <RotateTool /> : null}
        {route === "terms" ? <TermsPage /> : null}
        {route === "not-found" ? <NotFoundPage /> : null}
      </main>
      <Footer />
    </div>
  );
}

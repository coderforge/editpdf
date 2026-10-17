import { useEffect } from "react";
import termsEn from "../../../legal/terms.en.md?raw";
import termsIt from "../../../legal/terms.it.md?raw";
import { format, useI18n } from "../i18n";
import { Markdown } from "../legal/Markdown";
import { Link } from "../router";
import { TERMS_VERSION } from "../service";

export function TermsPage() {
  const { t, language, setLanguage } = useI18n();

  useEffect(() => {
    document.title = `${t.footer.terms} - editpdf`;
  }, [t]);

  return (
    <article className="legal">
      <nav className="legal__nav">
        <Link to="merge">← {t.terms.back}</Link>
        <button type="button" className="button button--link" onClick={() => setLanguage(language === "en" ? "it" : "en")}>
          {t.terms.other}
        </button>
      </nav>
      <p className="legal__version">{format(t.terms.version, { version: TERMS_VERSION })}</p>
      <Markdown source={language === "it" ? termsIt : termsEn} />
    </article>
  );
}

export function NotFoundPage() {
  const { t } = useI18n();
  return (
    <section className="not-found">
      <h1>{t.notFound.title}</h1>
      <Link to="merge" className="button button--primary">
        {t.notFound.back}
      </Link>
    </section>
  );
}

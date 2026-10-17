import { useEffect } from "react";
import terms from "../../../legal/terms.en.md?raw";
import { useI18n } from "../i18n";
import { Markdown } from "../legal/Markdown";
import { Link } from "../router";
import { TERMS_VERSION } from "../service";

export function TermsPage() {
  const { t } = useI18n();

  useEffect(() => {
    document.title = `${t.footer.terms} - editpdf`;
  }, [t]);

  return (
    <article className="legal">
      <nav className="legal__nav">
        <Link to="merge">← {t.terms.back}</Link>
      </nav>
      {t.terms.englishOnly === "" ? null : (
        <p className="notice notice--info">
          {t.terms.englishOnly}
        </p>
      )}
      <div lang="en">
        <p className="legal__version">Version of {TERMS_VERSION}</p>
        <Markdown source={terms} />
      </div>
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

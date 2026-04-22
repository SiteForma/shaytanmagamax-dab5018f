import { PageHeader, SectionTitle } from "@/components/ui-ext/PageHeader";
import { MagamaxLogo } from "@/components/brand/MagamaxLogo";

export default function SettingsPage() {
  return (
    <>
      <PageHeader eyebrow="Workspace" title="Settings" description="Personal defaults for theme, table density, reserve horizon, and brand asset status." />

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="panel p-5 space-y-4">
          <SectionTitle>Defaults</SectionTitle>
          {[
            { label: "Theme", control: <select className="rounded-md border border-line-subtle bg-surface-panel px-2 py-1 text-sm focus-ring"><option>Dark</option><option>Light</option></select> },
            { label: "Table density", control: <select className="rounded-md border border-line-subtle bg-surface-panel px-2 py-1 text-sm focus-ring"><option>Compact</option><option>Default</option><option>Comfortable</option></select> },
            { label: "Reserve horizon", control: <select className="rounded-md border border-line-subtle bg-surface-panel px-2 py-1 text-sm focus-ring"><option>3 months</option><option>2 months</option></select> },
            { label: "Safety factor", control: <span className="text-num text-sm">×1.10</span> },
            { label: "Default grouping", control: <select className="rounded-md border border-line-subtle bg-surface-panel px-2 py-1 text-sm focus-ring"><option>By client</option><option>By category</option><option>None</option></select> },
          ].map((r) => (
            <div key={r.label} className="flex items-center justify-between border-b border-line-subtle/60 pb-3 last:border-0">
              <span className="text-sm text-ink-secondary">{r.label}</span>
              {r.control}
            </div>
          ))}
        </div>

        <div className="panel p-5 space-y-4">
          <SectionTitle>Brand asset</SectionTitle>
          <div className="rounded-lg border border-line-subtle bg-surface-muted/50 p-4">
            <MagamaxLogo />
          </div>
          <p className="text-xs text-ink-muted">Source: <span className="text-num">magamax.ru/img/logo_magamax@2x.png</span> — official asset, not a recreation. Replace the file at <span className="text-num">src/assets/magamax-logo.png</span> to update.</p>
          <div className="flex items-center justify-between rounded-md border border-line-subtle bg-surface-muted/50 px-3 py-2 text-xs">
            <span className="text-ink-muted">Brand primary</span>
            <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm bg-brand" /><span className="text-num">#FF671F</span></span>
          </div>
        </div>
      </section>
    </>
  );
}

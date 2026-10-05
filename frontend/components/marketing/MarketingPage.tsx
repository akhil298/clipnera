import { BeforeAfter } from './BeforeAfter';
import { CaptionStyles } from './CaptionStyles';
import { ClosingCta } from './ClosingCta';
import { EditingSection } from './EditingSection';
import { ExampleOutput } from './ExampleOutput';
import { FaqSection } from './FaqSection';
import { HeroComposer } from './HeroComposer';
import { HowItWorks } from './HowItWorks';
import { Pricing } from './Pricing';
import { PublishSection } from './PublishSection';
import { Section } from './Section';

/**
 * The landing (`/`, with `/editor` merged in): a static server page whose only
 * client islands are the composer, the before/after slider, the caption picker,
 * pricing and the buttons that focus the composer.
 */
export function MarketingPage() {
  return (
    <main id="landing-main" tabIndex={-1} className="flex-1 focus-visible:outline-none">
      <section id="top" aria-labelledby="hero-title" className="scroll-mt-16 px-4 pb-24 pt-16 sm:px-8 sm:pt-24 lg:pb-32 lg:pt-32">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-6 text-center">
          <h1 id="hero-title" className="font-cn-sans text-cn-display-sm font-bold text-cn-fg sm:text-cn-display lg:text-cn-display-lg">
            Long video in. <span className="text-cn-accent-text">Shorts</span> out.
          </h1>
          <p className="max-w-2xl text-cn-body-lg text-cn-fg-secondary">
            Paste a YouTube link or add a video and say what you want. Clipnera finds the moments worth posting, reframes them to 9:16 around the speaker,
            cleans the audio and adds captions. You review before anything is posted.
          </p>
          <HeroComposer />
          <p className="text-cn-label text-cn-fg-muted">Free plan, no card needed · Direct posting to YouTube and Instagram</p>
        </div>
      </section>

      <ExampleOutput />
      <HowItWorks />

      <Section
        id="before-after"
        title="Drag the line. That’s the whole edit."
        intro="Left of the line is what a plain vertical export gives you. Right of it is the same moment after Clipnera."
        className="pt-0 lg:pt-0"
      >
        <BeforeAfter />
      </Section>

      <Section
        id="captions"
        title="Captions people actually read"
        intro="Most Shorts are watched on mute. Pick a style and the phone updates; every style lets you change colours, casing, line count and auto-emoji."
        className="pt-0 lg:pt-0"
      >
        <CaptionStyles />
      </Section>

      <EditingSection />
      <PublishSection />

      <Section
        id="pricing"
        title="Start free. Upgrade when it’s working."
        intro="Prices in Indian rupees; the amount shown is the amount you pay. Pro doesn’t renew on its own."
        centred
        className="pt-0 lg:pt-0"
      >
        <Pricing />
      </Section>

      <FaqSection />
      <ClosingCta />
    </main>
  );
}

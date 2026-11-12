import { TrackedWhatsappLink } from '@/components/shared/tracked-whatsapp-link';
import { getSiteConfig } from '@/lib/site-config';

interface WhatsappFabProps {
  readonly label: string;
}

export function WhatsappFab({ label }: WhatsappFabProps) {
  const { contact } = getSiteConfig();

  if (!contact.whatsappUrl) {
    return null;
  }

  return (
    <TrackedWhatsappLink
      href={contact.whatsappUrl}
      leadType="whatsapp_fab"
      className="whatsapp-fab link-unadorned fixed bottom-4 right-4 z-40 inline-flex min-h-12 min-w-12 items-center justify-center gap-2 rounded-full bg-brand-500 px-4 py-3 text-sm font-semibold text-ink-900 shadow-lg transition hover:bg-brand-600 sm:hidden"
      target="_blank"
      rel="noreferrer noopener"
    >
      <img
        src="/images/icons/chat.svg"
        alt=""
        width={20}
        height={20}
        aria-hidden="true"
        className="h-5 w-5 shrink-0"
      />
      <span className="whatsapp-fab__label">{label}</span>
    </TrackedWhatsappLink>
  );
}

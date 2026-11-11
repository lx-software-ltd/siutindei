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
      className="whatsapp-fab link-unadorned fixed bottom-4 right-4 z-40 inline-flex min-h-12 items-center rounded-full bg-brand-500 px-4 py-3 text-sm font-semibold text-ink-900 shadow-lg transition hover:bg-brand-600 sm:hidden"
      target="_blank"
      rel="noreferrer noopener"
    >
      {label}
    </TrackedWhatsappLink>
  );
}

'use client';

import { useEffect, useMemo, useState } from 'react';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { ActivityAbout } from '@/components/sections/activity-detail/activity-about';
import {
  ActivityBreadcrumb,
  type BreadcrumbItem,
} from '@/components/sections/activity-detail/activity-breadcrumb';
import {
  ActivityDetailEmpty,
  type ActivityDetailEmptyReason,
  ActivityDetailSkeleton,
} from '@/components/sections/activity-detail/activity-detail-states';
import {
  ActivityActionBar,
  ActivitySummaryCard,
  EnquiryLink,
  type EnquiryProps,
} from '@/components/sections/activity-detail/activity-enquiry';
import { ActivityGallery } from '@/components/sections/activity-detail/activity-gallery';
import { ActivityGoodToKnow } from '@/components/sections/activity-detail/activity-good-to-know';
import {
  ActivityKeyFacts,
  type KeyFact,
} from '@/components/sections/activity-detail/activity-key-facts';
import { ActivityLocation } from '@/components/sections/activity-detail/activity-location';
import { ActivityOrganiser } from '@/components/sections/activity-detail/activity-organiser';
import { ActivityPrice } from '@/components/sections/activity-detail/activity-price';
import { ActivityRelated } from '@/components/sections/activity-detail/activity-related';
import { ActivityReviews } from '@/components/sections/activity-detail/activity-reviews';
import { ActivityDates } from '@/components/sections/activity-detail/activity-dates';
import { ActivitySchedule } from '@/components/sections/activity-detail/activity-schedule';
import { ActivityTitleBlock } from '@/components/sections/activity-detail/activity-title-block';
import type { ListingCardLabels } from '@/components/sections/listings/listing-card';
import { ShareButton } from '@/components/shared/ui/share-button';
import { preloadActivityImage } from '@/lib/activity-image-preload';
import {
  buildEnquiryHref,
  listingAtVenue,
  venueFreeTrial,
  venueLanguages,
  venuePricings,
  venueVariants,
  venueWeeklyEntries,
} from '@/lib/activities/detail-view';
import {
  activityBreadcrumbItems,
  activityStructuredData,
} from '@/lib/activities/activity-page-data';
import { listingVenues } from '@/lib/activities/group-listings';
import {
  categoryLabelForListing,
  checkedFacts,
  directionsUrl,
  formatMonthYear,
  listingAgeLabel,
  listingLanguagesLabel,
  placeLabelForLocation,
  shortPlaceLabel,
} from '@/lib/activities/listing-facts';
import { logActivityLoadError } from '@/lib/activities/load-error';
import {
  isTemplateDescription,
  isTemporarilyClosed,
  listingImageIsLogo,
  listingImageUrls,
  listingOrgName,
  listingTitle,
  pickTranslation,
} from '@/lib/activities/listing-utils';
import { buildSearchPageHref } from '@/lib/activities/map-search-url';
import { formatClassEquivalent, formatListingPriceSummary } from '@/lib/activities/price-format';
import { loadLastSearchHref, rememberViewedActivity } from '@/lib/activities/recent-storage';
import { formatDatedSession, upcomingSessions } from '@/lib/activities/schedule-dates';
import { formatScheduleSummary } from '@/lib/activities/schedule-format';
import { fetchActivityListingById } from '@/lib/activities/search-client';
import { DEFAULT_SEARCH_FILTERS } from '@/lib/activities/search-params';
import type { ActivityListing } from '@/lib/activities/types';
import { itemFieldsFromListing, trackViewItem } from '@/lib/analytics/data-layer';
import { formatTemplate } from '@/lib/format-template';
import { homeWizardChoices } from '@/lib/home-wizard/choices';
import { iconSrcForListing } from '@/lib/home-wizard/choice-icons';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';
import { getSiteConfig } from '@/lib/site-config';

interface ActivityDetailPageProps {
  readonly locale: Locale;
  readonly activityId: string;
  readonly copy: SiteContent['activityDetail'];
  /** The build's copy, so the exported HTML has the activity in it. */
  readonly initialListing?: ActivityListing | null;
  /** Activity types with a landing page, for the breadcrumb. */
  readonly landingTypeIds?: readonly string[];
}

type Copy = SiteContent['activityDetail'];

function cardLabels(copy: Copy): ListingCardLabels {
  return {
    parentVerified: copy.parentVerifiedLabel,
    freeTrial: copy.listingFreeTrialLabel,
    imageFallback: copy.imageFallbackLabel,
    locationsCount: copy.locationsCountLabel,
    detailsOnRequest: copy.askForPriceLabel,
  };
}

export function ActivityDetailPage({
  locale,
  activityId,
  copy,
  initialListing = null,
  landingTypeIds = [],
}: ActivityDetailPageProps) {
  const prerendered = initialListing?.activity.id === activityId ? initialListing : null;
  const [listing, setListing] = useState<ActivityListing | null>(prerendered);
  const [isLoading, setIsLoading] = useState(prerendered === null);
  const [emptyReason, setEmptyReason] = useState<ActivityDetailEmptyReason | null>(null);
  const [selectedVenueId, setSelectedVenueId] = useState<string | null>(null);
  const [backHref, setBackHref] = useState<string | null>(null);
  const [organiserActivityIds, setOrganiserActivityIds] = useState<readonly string[]>([]);
  const { contact, siteName } = getSiteConfig();

  useEffect(() => {
    setBackHref(loadLastSearchHref());
  }, []);

  useEffect(() => {
    let cancelled = false;
    const hasPrerendered = prerendered !== null;
    if (!hasPrerendered) {
      setIsLoading(true);
    }
    setEmptyReason(null);
    setSelectedVenueId(null);
    setOrganiserActivityIds([]);

    fetchActivityListingById(activityId)
      .then((item) => {
        if (cancelled) {
          return;
        }
        if (!item) {
          setEmptyReason('notFound');
          setListing(null);
          return;
        }
        setListing(item);
        rememberViewedActivity(item.activity.id);
      })
      .catch((error: unknown) => {
        logActivityLoadError('activity detail', error);
        // A pre-rendered page keeps the build's copy, for example when a
        // crawler is not allowed to call the search API.
        if (!cancelled && !hasPrerendered) {
          setEmptyReason('error');
          setListing(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activityId, prerendered]);

  const imageUrls = useMemo(() => (listing ? listingImageUrls(listing) : []), [listing]);
  const firstImageUrl = imageUrls[0] ?? null;

  useEffect(() => {
    if (!firstImageUrl) {
      return undefined;
    }
    return preloadActivityImage(firstImageUrl);
  }, [firstImageUrl]);

  useEffect(() => {
    if (!listing || prerendered) {
      return undefined;
    }
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.textContent = JSON.stringify(activityStructuredData(locale, listing, imageUrls));
    document.head.appendChild(script);

    // The `?id=` page is one generic export; give each activity a real
    // tab title once its data loads. Pre-rendered pages have their own.
    const previousTitle = document.title;
    document.title = `${listingTitle(locale, listing)} · ${siteName}`;

    return () => {
      script.remove();
      document.title = previousTitle;
    };
  }, [imageUrls, listing, locale, prerendered, siteName]);

  useEffect(() => {
    if (!listing) {
      return;
    }
    trackViewItem(locale, listing);
  }, [listing, locale]);

  if (isLoading) {
    return <ActivityDetailSkeleton copy={copy} />;
  }

  if (!listing || emptyReason) {
    return (
      <>
        <meta name="robots" content="noindex" />
        <ActivityDetailEmpty locale={locale} reason={emptyReason ?? 'notFound'} copy={copy} />
      </>
    );
  }

  const venues = listingVenues(listing).map((variant) => variant.location);
  const venueId = selectedVenueId ?? venues[0]?.id ?? listing.location.id;
  const variants = venueVariants(listing, venueId);
  const atVenue = listingAtVenue(listing, venueId);
  const title = listingTitle(locale, listing);
  const orgName = listingOrgName(locale, listing);
  const isTemplate = isTemplateDescription(listing);
  const description = isTemplate
    ? ''
    : pickTranslation(
        locale,
        listing.activity.description ?? '',
        listing.activity.descriptionTranslations,
      );
  const organiserDescription = isTemplate
    ? ''
    : pickTranslation(
        locale,
        listing.organization.description ?? '',
        listing.organization.descriptionTranslations ?? {},
      );
  const pricings = venuePricings(variants);
  const hasFreeTrial = venueFreeTrial(variants);
  const entries = venueWeeklyEntries(variants);
  const sessions = upcomingSessions(variants);
  const nextSession = sessions[0]?.schedule;
  const price = formatListingPriceSummary(locale, atVenue);
  const kind = listing.activity.kind;
  const opensForVisits = kind === 'place' || kind === 'eat';
  const languages = opensForVisits ? [] : venueLanguages(variants);
  const priceDetail = pricings[0]
    ? formatClassEquivalent(locale, pricings[0], kind)
    : null;
  const scheduleCopy = opensForVisits
    ? {
        ...copy,
        scheduleHeading: copy.openingHoursHeading,
        scheduleMissingLabel: copy.openingHoursMissingLabel,
      }
    : copy;
  const categoryLabel = categoryLabelForListing(locale, listing);
  const venue = atVenue.location;
  const where =
    venue.name ??
    (venues.length > 1
      ? formatTemplate(copy.locationsCountLabel, { count: venues.length })
      : placeLabelForLocation(locale, venue));
  const facts: readonly KeyFact[] = [
    ...(opensForVisits
      ? []
      : [{ id: 'ages', icon: 'age', value: listingAgeLabel(locale, listing) } as const]),
    {
      id: opensForVisits ? 'hours' : 'when',
      icon: 'calendar',
      value: nextSession
        ? formatDatedSession(locale, nextSession)
        : formatScheduleSummary(locale, entries),
    },
    {
      id: 'where',
      icon: 'pin',
      value: where,
      detail: venue.name ? placeLabelForLocation(locale, venue) : null,
    },
    { id: 'price', icon: 'price', value: price, detail: priceDetail },
    { id: 'language', icon: 'language', value: listingLanguagesLabel(locale, languages) },
  ];
  const enquiry: EnquiryProps = {
    href: buildEnquiryHref(contact.whatsappUrl, listing, locale),
    item: itemFieldsFromListing(locale, listing),
    locationId: venue.id,
    activityId: listing.activity.id,
    label: copy.whatsappCtaLabel,
  };
  const directionsHref = directionsUrl(venue, venues.length === 1 ? listing.organization.placeId : null);
  const labels = cardLabels(copy);
  const similarParams = listing.activity.categoryId
    ? {
        categoryIds: [listing.activity.categoryId],
        areaId: venue.regionAreaId ?? venue.areaId,
      }
    : null;

  return (
    <article
      className="activity-detail mx-auto max-w-6xl px-4 pb-14 pt-2 sm:px-6 lg:px-8 lg:pb-8 short:pb-5"
    >
      <ActivityBreadcrumb
        backHref={backHref}
        items={activityBreadcrumbItems(locale, listing, copy, landingTypeIds)}
        copy={copy}
      />
      <div className="mt-2 grid gap-x-8 gap-y-6 short:grid-cols-2 short:items-start short:gap-x-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 short:col-start-1 short:row-start-1 lg:col-span-2">
          <ActivityGallery
            title={title}
            imageUrls={imageUrls}
            isLogo={listingImageIsLogo(listing)}
            fallbackIconSrc={iconSrcForListing(listing.activity)}
            copy={copy}
          />
        </div>
        <div className="min-w-0 short:col-start-2 short:row-start-1 lg:col-start-1 lg:row-start-2">
          <ActivityTitleBlock
            title={title}
            categoryLabel={categoryLabel}
            categoryIconSrc={categoryLabel ? iconSrcForListing(listing.activity) : null}
            organiserName={orgName}
            organiserLogoUrl={listing.organization.logoMediaUrl}
            isTemporarilyClosed={isTemporarilyClosed(atVenue)}
            hasFreeTrial={hasFreeTrial}
            isParentVerified={listing.organization.parentVerified === true}
            checkedDate={formatMonthYear(locale, listing.organization.parentVerifiedAt)}
            rating={listing.organization.rating ?? null}
            copy={copy}
            actions={
              <div className="flex flex-wrap items-center gap-2 lg:hidden">
                {price ? (
                  <p className="hidden w-full text-lg font-semibold text-ink-900 short:block">
                    {price}
                  </p>
                ) : null}
                <span className="hidden short:contents">
                  <EnquiryLink enquiry={enquiry} />
                </span>
                <ShareButton title={title} label={copy.shareLabel} copiedLabel={copy.linkCopiedLabel} />
              </div>
            }
          />
        </div>
        <div className="min-w-0 max-w-3xl space-y-6 short:col-span-2 lg:col-start-1 lg:row-start-3">
          <ActivityKeyFacts facts={facts} copy={copy} enquiryHref={enquiry.href} />
          <ActivityAbout description={description} isTemplate={isTemplate} copy={copy} />
          <ActivityGoodToKnow facts={checkedFacts(listing)} copy={copy} />
          {sessions.length > 0 ? (
            <ActivityDates
              locale={locale}
              sessions={sessions}
              languages={languages}
              copy={copy}
            />
          ) : (
            <ActivitySchedule
              locale={locale}
              entries={entries}
              languages={languages}
              copy={scheduleCopy}
            />
          )}
          <ActivityPrice
            locale={locale}
            pricings={pricings}
            kind={kind}
            hasFreeTrial={hasFreeTrial}
            copy={copy}
          />
          <ActivityLocation
            locale={locale}
            venues={venues}
            selectedId={venue.id}
            onSelect={setSelectedVenueId}
            placeId={listing.organization.placeId ?? null}
            copy={copy}
          />
          <ActivityOrganiser
            locale={locale}
            name={orgName}
            description={organiserDescription}
            logoUrl={listing.organization.logoMediaUrl}
            contact={listing.organization.contact ?? null}
            updatedAt={listing.organization.updatedAt ?? null}
            copy={copy}
          />
          <ActivityReviews
            locale={locale}
            rating={listing.organization.rating ?? null}
            reviews={listing.organization.reviews ?? []}
            copy={copy}
          />
        </div>
        <div className="hidden lg:col-start-2 lg:row-span-2 lg:row-start-2 lg:block short:hidden">
          <ActivitySummaryCard
            price={price}
            priceDetail={priceDetail}
            facts={facts}
            enquiry={enquiry}
            directionsHref={directionsHref}
            title={title}
            copy={copy}
          />
        </div>
      </div>
      <div className="mt-8 space-y-8">
        <ActivityRelated
          locale={locale}
          id="more-from-organiser"
          title={formatTemplate(copy.moreFromOrganiserHeading, { name: orgName })}
          params={{ organizationIds: [listing.organization.id] }}
          excludeIds={[listing.activity.id]}
          onLoaded={setOrganiserActivityIds}
          labels={labels}
          previousLabel={copy.previousPhotoLabel}
          nextLabel={copy.nextPhotoLabel}
        />
        <ActivityRelated
          locale={locale}
          id="similar"
          title={copy.similarHeading}
          params={similarParams}
          excludeIds={[listing.activity.id, ...organiserActivityIds]}
          labels={labels}
          previousLabel={copy.previousPhotoLabel}
          nextLabel={copy.nextPhotoLabel}
        />
      </div>
      <ActivityActionBar price={price} enquiry={enquiry} />
    </article>
  );
}

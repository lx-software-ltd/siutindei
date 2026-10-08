import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../config/tokens/tokens.dart';
import '../../../core/core.dart';
import '../../../domain/entities/entities.dart';

/// Activity card widget using leaf tokens and domain entities.
///
/// Architecture:
/// - Uses domain entities (ActivitySearchResultEntity) for type safety
/// - Follows Flutter architecture guidelines
///
/// Performance optimizations applied:
/// - Uses `select` for granular provider watching
/// - Extracts child widgets to separate classes to minimize rebuilds
/// - Caches computed values where possible
/// - Uses const constructors where possible
///
/// See: https://docs.flutter.dev/app-architecture/guide
class ActivityCard extends ConsumerWidget {
  const ActivityCard({
    super.key,
    required this.result,
    this.onTap,
    this.onOrganizationTap,
  });

  final ActivitySearchResultEntity result;
  final VoidCallback? onTap;
  final VoidCallback? onOrganizationTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Use select to only rebuild when specific tokens change
    final tokens = ref.watch(
      componentTokensProvider.select((t) => t.activityCard),
    );
    final priceTokens = ref.watch(
      componentTokensProvider.select((t) => t.priceTag),
    );
    final spacing = ref.watch(semanticTokensProvider.select((s) => s.spacing));
    final textStyles = ref.watch(semanticTokensProvider.select((s) => s.text));

    // Cache border radius to avoid recreating
    final borderRadius = BorderRadius.circular(tokens.borderRadius);

    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: spacing.md,
        vertical: spacing.sm,
      ),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: tokens.background,
          borderRadius: borderRadius,
          border: Border.all(color: tokens.border),
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onTap,
            borderRadius: borderRadius,
            child: Padding(
              padding: EdgeInsets.all(tokens.padding),
              child: _ActivityCardContent(
                result: result,
                tokens: tokens,
                priceTokens: priceTokens,
                spacing: spacing,
                textStyles: textStyles,
                onOrganizationTap: onOrganizationTap,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Extracted content widget to isolate rebuilds.
class _ActivityCardContent extends StatelessWidget {
  const _ActivityCardContent({
    required this.result,
    required this.tokens,
    required this.priceTokens,
    required this.spacing,
    required this.textStyles,
    this.onOrganizationTap,
  });

  final ActivitySearchResultEntity result;
  final ActivityCardTokens tokens;
  final PriceTagTokens priceTokens;
  final SemanticSpacing spacing;
  final SemanticText textStyles;
  final VoidCallback? onOrganizationTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        _ActivityCardHeader(
          result: result,
          tokens: tokens,
          onOrganizationTap: onOrganizationTap,
        ),
        SizedBox(height: tokens.gap),
        _ActivityCardInfo(result: result, tokens: tokens),
        SizedBox(height: tokens.gap),
        _ActivityCardSchedulePrice(
          result: result,
          tokens: tokens,
          priceTokens: priceTokens,
          spacing: spacing,
        ),
        if (result.activity.description != null) ...[
          SizedBox(height: tokens.gap),
          Text(
            result.activity.description!,
            style: textStyles.bodySmall.copyWith(height: 1.4),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
        SizedBox(height: tokens.gap),
        _ActivityCardTags(result: result),
      ],
    );
  }
}

/// Header with avatar and organization info.
class _ActivityCardHeader extends StatelessWidget {
  const _ActivityCardHeader({
    required this.result,
    required this.tokens,
    this.onOrganizationTap,
  });

  final ActivitySearchResultEntity result;
  final ActivityCardTokens tokens;
  final VoidCallback? onOrganizationTap;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        BaseAvatar(
          name: result.organization.name,
          imageUrl: result.organization.primaryMediaUrl,
          size: AvatarSize.md,
        ),
        SizedBox(width: tokens.gap),
        Expanded(
          child: GestureDetector(
            onTap: onOrganizationTap,
            behavior: HitTestBehavior.opaque,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  result.organization.name,
                  style: TextStyle(
                    fontSize: tokens.organizationFontSize,
                    fontWeight: FontWeight.w500,
                    color: tokens.organizationColor,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Row(
                  children: [
                    Icon(
                      Icons.location_on_outlined,
                      size: 14,
                      color: tokens.locationIconColor,
                    ),
                    const SizedBox(width: 2),
                    Expanded(
                      child: Text(
                        result.location.address ?? result.location.areaId,
                        style: TextStyle(
                          fontSize: tokens.locationFontSize,
                          color: tokens.locationColor,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// Activity name and age info.
class _ActivityCardInfo extends StatelessWidget {
  const _ActivityCardInfo({required this.result, required this.tokens});

  final ActivitySearchResultEntity result;
  final ActivityCardTokens tokens;

  @override
  Widget build(BuildContext context) {
    final ageRange = result.activity.ageRangeDisplay;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          result.activity.name,
          style: TextStyle(
            fontSize: tokens.titleFontSize,
            fontWeight: tokens.titleFontWeight,
            color: tokens.titleColor,
          ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        if (ageRange != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: _AgeTag(ageRange: ageRange, tokens: tokens),
          ),
      ],
    );
  }
}

/// Schedule and price row.
class _ActivityCardSchedulePrice extends StatelessWidget {
  const _ActivityCardSchedulePrice({
    required this.result,
    required this.tokens,
    required this.priceTokens,
    required this.spacing,
  });

  final ActivitySearchResultEntity result;
  final ActivityCardTokens tokens;
  final PriceTagTokens priceTokens;
  final SemanticSpacing spacing;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _ScheduleInfo(schedule: result.schedule, tokens: tokens),
        ),
        SizedBox(width: spacing.md),
        _PriceTag(pricing: result.pricing, tokens: priceTokens),
      ],
    );
  }
}

/// Language and pricing type tags.
class _ActivityCardTags extends StatelessWidget {
  const _ActivityCardTags({required this.result});

  final ActivitySearchResultEntity result;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        for (final lang in result.schedule.languages.take(3))
          BaseBadge(label: lang.toUpperCase()),
        BaseBadge(
          label: _getPricingTypeLabel(result.pricing.type),
          variant: BadgeVariant.success,
        ),
      ],
    );
  }

  String _getPricingTypeLabel(PricingType type) {
    return switch (type) {
      PricingType.perClass => 'Per Class',
      PricingType.perSessions => 'Per Term',
      PricingType.perHour => 'Hourly',
      PricingType.perDay => 'Daily',
      PricingType.free => 'Free',
    };
  }
}

/// Age display tag - extracted as StatelessWidget.
class _AgeTag extends StatelessWidget {
  const _AgeTag({required this.ageRange, required this.tokens});

  final String ageRange;
  final ActivityCardTokens tokens;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.child_care, size: 14, color: tokens.ageForeground),
        const SizedBox(width: 4),
        Text(
          ageRange,
          style: TextStyle(
            fontSize: tokens.ageFontSize,
            color: tokens.ageForeground,
          ),
        ),
      ],
    );
  }
}

/// Schedule info display - extracted as StatelessWidget.
class _ScheduleInfo extends StatelessWidget {
  const _ScheduleInfo({required this.schedule, required this.tokens});

  final ScheduleEntity schedule;
  final ActivityCardTokens tokens;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(Icons.schedule, size: 16, color: tokens.scheduleIconColor),
        const SizedBox(width: 4),
        Expanded(
          child: Text(
            _formatSchedule(),
            style: TextStyle(
              fontSize: tokens.scheduleFontSize,
              color: tokens.scheduleColor,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }

  String _formatSchedule() {
    final parts = <String>[];

    // Day of week or month
    final dayName = schedule.dayOfWeekName;
    if (dayName != null) {
      parts.add(dayName.substring(0, 3)); // Short name
    } else if (schedule.dayOfMonth != null) {
      parts.add('Day ${schedule.dayOfMonth}');
    }

    // Time
    final timeStr = schedule.formattedTime;
    if (timeStr != null) {
      parts.add(timeStr);
    }

    if (parts.isEmpty) {
      return switch (schedule.type) {
        ScheduleType.dateSpecific => 'One-time event',
        _ => 'See details',
      };
    }

    return parts.join(' • ');
  }
}

/// Price tag display - extracted as StatelessWidget.
class _PriceTag extends StatelessWidget {
  const _PriceTag({required this.pricing, required this.tokens});

  final PricingEntity pricing;
  final PriceTagTokens tokens;

  @override
  Widget build(BuildContext context) {
    // Cache border radius
    final borderRadius = BorderRadius.circular(tokens.borderRadius);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: tokens.background,
        borderRadius: borderRadius,
      ),
      child: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: tokens.paddingHorizontal,
          vertical: tokens.paddingVertical,
        ),
        child: Text(
          pricing.formattedPrice,
          style: TextStyle(
            fontSize: tokens.fontSize,
            fontWeight: tokens.fontWeight,
            color: tokens.foreground,
          ),
        ),
      ),
    );
  }
}

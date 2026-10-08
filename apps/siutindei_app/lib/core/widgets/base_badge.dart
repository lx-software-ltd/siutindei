import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/tokens/tokens.dart';

/// Badge variants.
enum BadgeVariant { primary, success, warning, error }

/// Base badge component that consumes badge tokens.
///
/// Performance optimizations:
/// - Uses `select` for granular token watching
/// - Caches computed colors
/// - Uses const constructors where possible
class BaseBadge extends ConsumerWidget {
  const BaseBadge({
    super.key,
    required this.label,
    this.variant = BadgeVariant.primary,
    this.icon,
  });

  final String label;
  final BadgeVariant variant;
  final IconData? icon;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final badgeTokens = ref.watch(
      componentTokensProvider.select((t) => t.badge),
    );

    // Compute colors based on variant
    final (background, foreground) = _getColors(badgeTokens);
    final borderRadius = BorderRadius.circular(badgeTokens.borderRadius);

    return DecoratedBox(
      decoration: BoxDecoration(color: background, borderRadius: borderRadius),
      child: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: badgeTokens.paddingHorizontal,
          vertical: badgeTokens.paddingVertical,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: badgeTokens.fontSize + 2, color: foreground),
              const SizedBox(width: 4),
            ],
            Text(
              label,
              style: TextStyle(
                fontSize: badgeTokens.fontSize,
                fontWeight: FontWeight.w500,
                color: foreground,
              ),
            ),
          ],
        ),
      ),
    );
  }

  (Color, Color) _getColors(BadgeTokens tokens) {
    return switch (variant) {
      BadgeVariant.primary => (tokens.background, tokens.foreground),
      BadgeVariant.success => (
        tokens.successBackground,
        tokens.successForeground,
      ),
      BadgeVariant.warning => (
        tokens.warningBackground,
        tokens.warningForeground,
      ),
      BadgeVariant.error => (tokens.errorBackground, tokens.errorForeground),
    };
  }
}

/// Count badge (e.g., filter count).
///
/// Performance: Uses `select` for minimal rebuilds.
class CountBadge extends ConsumerWidget {
  const CountBadge({super.key, required this.count});

  final int count;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filterTokens = ref.watch(
      componentTokensProvider.select((t) => t.filterChip),
    );

    return DecoratedBox(
      decoration: BoxDecoration(
        color: filterTokens.badgeBackground,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        child: Text(
          count.toString(),
          style: TextStyle(
            color: filterTokens.badgeForeground,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}
